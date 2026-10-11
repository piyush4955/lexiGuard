"""
Document classification and analysis-quality tests for LexiGuard.

Tests verify that:
 - Legal contracts receive the full legal-contract analysis structure.
 - Academic documents receive an academic summary without fabricated legal output.
 - 'other' documents receive a neutral analysis.
 - Missing party names are distinguished from non-applicable parties.
 - Invalid categories and malformed AI output are handled correctly.
 - Non-contract scores never default to 7.5/10 (or any hardcoded value).
 - MongoDB persistence and sharing remain operational across all categories.
 - Existing Gemini retry/timeout/failure behaviour is preserved.

All Gemini calls are mocked for determinism.
"""

import os
import sys
import json
import io
import pytest
import mongomock
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app import app
import app as app_module
from db import (
    MongoDBManager,
    DocumentRepository,
    AnalysisRepository,
    SharedAnalysisRepository,
    init_indexes,
)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Flask test client with isolated in-memory mongomock database."""
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["lexiguard"]

    with patch.object(MongoDBManager, 'get_client', return_value=mock_client), \
         patch.object(MongoDBManager, 'get_database', return_value=mock_db), \
         patch.dict(os.environ, {"MONGODB_URI": "mongodb://localhost:27017", "MONGODB_DATABASE": "lexiguard"}), \
         patch.object(app_module, 'USE_MONGODB', True):

        MongoDBManager._client = mock_client
        MongoDBManager._db = mock_db
        init_indexes()

        app.config['TESTING'] = True
        with app.test_client() as test_client:
            yield test_client

        MongoDBManager._client = None
        MongoDBManager._db = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def post_analyze(client, mock_ai_dict, doc_text="Valid document text long enough to pass the 20-char check."):
    """Helper: POST /analyze with a mocked Gemini response and dummy PDF."""
    with patch('app.get_gemini_response', return_value=json.dumps(mock_ai_dict)), \
         patch('app.extract_text_from_file', return_value=doc_text):
        data = {
            'language': 'English',
            'tags': 'test',
            'document': (io.BytesIO(b"dummy bytes"), "test_document.pdf"),
        }
        return client.post('/analyze', data=data, content_type='multipart/form-data')


# ---------------------------------------------------------------------------
# 1. Legal contract retains the established analysis structure
# ---------------------------------------------------------------------------

class TestContractDocumentAnalysis:
    """A genuine legal contract must retain the full legal analysis fields."""

    CONTRACT_AI = {
        "doc_category": "contract",
        "doc_type": "Rental Agreement",
        "detected_jurisdiction": "Karnataka, India",
        "sentiment": "Neutral",
        "key_info": {
            "readability_score": 7,
            "fairness_score": 6,
            "score_justification": "Strict forfeiture clause disadvantages tenant.",
            "parties": "Ramesh Kumar (Landlord) & Ananya Sharma (Tenant)",
            "financial_terms": "Rent: Rs. 35,000/mo, Deposit: Rs. 2,00,000",
            "tenure": "11 Months",
        },
        "summary_and_checklist": "### Key Summary\n- 11-month tenancy.\n\n### Action Checklist\n1. Negotiate lock-in clause.",
        "risk_analysis": "### Risk Radar & Flagged Gotchas\n1. Unilateral deposit forfeiture.",
        "questions_to_ask": "Can we reduce the early exit penalty?",
        "legal_formalities_guidance": "Stamp duty: 0.5% of annual rent in Karnataka.",
        "missing_clauses": "1. Force majeure clause absent.",
    }

    def test_contract_returns_200_with_all_required_fields(self, client):
        resp = post_analyze(client, self.CONTRACT_AI)
        assert resp.status_code == 200
        data = resp.get_json()
        for field in ["doc_id", "doc_category", "doc_type", "detected_jurisdiction",
                      "key_info", "summary_and_checklist",
                      "risk_analysis", "questions_to_ask", "legal_formalities_guidance", "missing_clauses"]:
            assert field in data, f"Missing field: {field}"
        assert data["doc_type"] == "Rental Agreement"
        assert data["detected_jurisdiction"] == "Karnataka, India"

    def test_contract_doc_category_is_contract(self, client):
        resp = post_analyze(client, self.CONTRACT_AI)
        data = resp.get_json()
        assert data["doc_category"] == "contract"
        assert data["key_info"]["doc_category"] == "contract"

    def test_contract_fairness_score_preserved_numeric(self, client):
        resp = post_analyze(client, self.CONTRACT_AI)
        data = resp.get_json()
        score = data["key_info"].get("fairness_score")
        assert score is not None, "Contract fairness_score must not be None"
        assert isinstance(score, (int, float)), "fairness_score must be numeric for contracts"
        assert 1 <= score <= 10, f"fairness_score {score} out of valid range"

    def test_contract_parties_present(self, client):
        resp = post_analyze(client, self.CONTRACT_AI)
        data = resp.get_json()
        parties = data["key_info"].get("parties", "")
        assert "Ramesh Kumar" in parties

    def test_contract_persisted_to_mongodb(self, client):
        resp = post_analyze(client, self.CONTRACT_AI)
        doc_id = resp.get_json()["doc_id"]
        record = AnalysisRepository.find_by_doc_id(doc_id)
        assert record is not None
        assert record["doc_category"] == "contract"
        assert record["doc_type"] == "Rental Agreement"


# ---------------------------------------------------------------------------
# 2. Academic document receives academic summary -- no fabricated legal output
# ---------------------------------------------------------------------------

class TestAcademicDocumentAnalysis:
    """Academic documents must not receive fabricated legal-contract analysis."""

    ACADEMIC_AI = {
        "doc_category": "academic_informational",
        "doc_type": "Lecture Notes - Software Project Management",
        "detected_jurisdiction": "Not applicable",
        "sentiment": "Informational",
        "key_info": {
            "readability_score": 8,
            "fairness_score": None,
            "score_justification": "Not applicable - this is not a legal contract",
            "parties": "Invented Company & Customer",
            "financial_terms": "$10,000 per month",
            "tenure": "One year",
            "subject": "Software Project Management",
            "document_scope": "Covers SDLC phases, estimation techniques, and risk management.",
            "source_type": "Lecture Notes",
        },
        "summary_and_checklist": "### Key Concepts\n- SDLC phases.\n- Risk management.\n\n### Study Checklist\n1. Review estimation techniques.",
        "risk_analysis": "### Key Caveats & Limitations\n- Concepts may be simplified for introductory level.",
        "questions_to_ask": "1. What are the main phases of the SDLC?\n2. How is project risk quantified?",
        "legal_formalities_guidance": "Not applicable - this document is not a legal contract.",
        "missing_clauses": "Not applicable - this is not a contract.",
    }

    def test_academic_returns_200(self, client):
        resp = post_analyze(client, self.ACADEMIC_AI)
        assert resp.status_code == 200

    def test_academic_doc_category_is_academic_informational(self, client):
        resp = post_analyze(client, self.ACADEMIC_AI)
        data = resp.get_json()
        assert data["doc_category"] == "academic_informational"

    def test_academic_fairness_score_is_null(self, client):
        """Non-contract documents must never carry a numeric fairness score."""
        resp = post_analyze(client, self.ACADEMIC_AI)
        data = resp.get_json()
        score = data["key_info"].get("fairness_score")
        assert score is None, f"Academic doc must not have numeric fairness_score, got: {score}"

    def test_academic_score_is_not_7_5_default(self, client):
        """Specifically guard against the old 7.5/10 hardcoded fallback."""
        resp = post_analyze(client, self.ACADEMIC_AI)
        data = resp.get_json()
        score = data["key_info"].get("fairness_score")
        assert score != 7.5, "Score must not fall back to hardcoded 7.5"
        assert score != "7.5/10", "Score must not fall back to '7.5/10' string"

    def test_academic_legal_formalities_is_not_applicable(self, client):
        resp = post_analyze(client, self.ACADEMIC_AI)
        data = resp.get_json()
        guidance = data.get("legal_formalities_guidance", "")
        assert "not applicable" in guidance.lower() or "not a legal contract" in guidance.lower()

    def test_academic_missing_clauses_is_not_applicable(self, client):
        resp = post_analyze(client, self.ACADEMIC_AI)
        data = resp.get_json()
        missing = data.get("missing_clauses", "")
        assert "not applicable" in missing.lower() or "not a contract" in missing.lower()
        for field in ["parties", "financial_terms", "tenure"]:
            assert field not in data["key_info"]

    def test_academic_persisted_with_correct_category(self, client):
        resp = post_analyze(client, self.ACADEMIC_AI)
        doc_id = resp.get_json()["doc_id"]
        record = AnalysisRepository.find_by_doc_id(doc_id)
        assert record is not None
        assert record["doc_category"] == "academic_informational"


# ---------------------------------------------------------------------------
# 3. 'other' document receives a neutral analysis
# ---------------------------------------------------------------------------

class TestOtherDocumentAnalysis:
    OTHER_AI = {
        "doc_category": "other",
        "doc_type": "Personal Letter",
        "detected_jurisdiction": "Not applicable",
        "sentiment": "Neutral",
        "key_info": {
            "readability_score": 9,
            "fairness_score": None,
            "score_justification": "Not applicable - this is not a legal contract",
            "document_description": "A personal letter from one individual to another.",
        },
        "summary_and_checklist": "This appears to be a personal letter discussing informal arrangements.",
        "risk_analysis": "No significant concerns for a personal letter.",
        "questions_to_ask": "1. Is any agreement here intended to be legally binding?",
        "legal_formalities_guidance": "Not applicable - this document does not have legal formalities.",
        "missing_clauses": "Not applicable - this is not a contract.",
    }

    def test_other_returns_200(self, client):
        resp = post_analyze(client, self.OTHER_AI)
        assert resp.status_code == 200

    def test_other_doc_category(self, client):
        resp = post_analyze(client, self.OTHER_AI)
        assert resp.get_json()["doc_category"] == "other"

    def test_other_fairness_score_is_null(self, client):
        resp = post_analyze(client, self.OTHER_AI)
        score = resp.get_json()["key_info"].get("fairness_score")
        assert score is None


# ---------------------------------------------------------------------------
# 4. Missing party names vs. non-applicable parties
# ---------------------------------------------------------------------------

class TestPartyNameDistinction:
    """Distinguish 'not found' from 'not applicable'."""

    def test_contract_with_missing_parties_says_not_found(self, client):
        """A contract that doesn't name parties should say 'Not found in document'."""
        ai = {
            "doc_category": "contract",
            "doc_type": "Service Agreement",
            "detected_jurisdiction": "General",
            "sentiment": "Neutral",
            "key_info": {
                "readability_score": 6,
                "fairness_score": 5,
                "score_justification": "Standard service terms.",
                "financial_terms": "Not found in document",
                "tenure": "Not found in document",
            },
            "summary_and_checklist": "Standard service agreement.",
            "risk_analysis": "No specific risks identified.",
            "questions_to_ask": "Who are the contracting parties?",
            "legal_formalities_guidance": "Not determined - jurisdiction unclear",
            "missing_clauses": "Party identification is absent.",
        }
        resp = post_analyze(client, ai)
        assert resp.status_code == 200
        data = resp.get_json()
        parties = data["key_info"].get("parties", "")
        assert "not found" in parties.lower(), f"Expected 'not found', got: {parties}"
        assert "not applicable" not in parties.lower(), \
            "Contract missing parties should say 'not found', not 'not applicable'"

    def test_academic_parties_field_absent(self, client):
        """Academic documents should not have a 'parties' field."""
        ai = {
            "doc_category": "academic_informational",
            "doc_type": "Research Paper",
            "detected_jurisdiction": "Not applicable",
            "sentiment": "Informational",
            "key_info": {
                "readability_score": 7,
                "fairness_score": None,
                "score_justification": "Not applicable - this is not a legal contract",
                "subject": "Machine Learning",
                "document_scope": "Introductory ML concepts.",
                "source_type": "Research Paper",
            },
            "summary_and_checklist": "Covers ML concepts.",
            "risk_analysis": "### Key Caveats\n- Theoretical, not empirically validated.",
            "questions_to_ask": "What algorithms are covered?",
            "legal_formalities_guidance": "Not applicable.",
            "missing_clauses": "Not applicable.",
        }
        resp = post_analyze(client, ai)
        assert resp.status_code == 200
        key_info = resp.get_json()["key_info"]
        assert "parties" not in key_info, "Academic doc must not have a 'parties' field"


# ---------------------------------------------------------------------------
# 5. Invalid or missing category is rejected
# ---------------------------------------------------------------------------

class TestInvalidCategory:
    def test_invalid_category_returns_503_without_persistence(self, client):
        ai = {
            "doc_category": "nonsense_value",
            "doc_type": "Unknown",
            "detected_jurisdiction": "Unknown",
            "sentiment": "Neutral",
            "key_info": {
                "readability_score": 5,
                "fairness_score": None,
                "score_justification": "Not applicable",
                "document_description": "Unknown document type.",
            },
            "summary_and_checklist": "Summary of unknown document.",
            "risk_analysis": "No risks identified.",
            "questions_to_ask": "What is this document?",
            "legal_formalities_guidance": "Not applicable.",
            "missing_clauses": "Not applicable.",
        }
        resp = post_analyze(client, ai)
        assert resp.status_code == 503
        assert "error" in resp.get_json()
        assert DocumentRepository.collection().count_documents({"filename": "test_document.pdf"}) == 0

    def test_missing_category_returns_503(self, client):
        ai = {
            "doc_type": "Unclassified Document",
            "detected_jurisdiction": "Not applicable",
            "sentiment": "Neutral",
            "key_info": {"readability_score": 5},
            "summary_and_checklist": "Summary.",
            "risk_analysis": "Caveats.",
            "questions_to_ask": "Questions.",
            "legal_formalities_guidance": "Not applicable.",
            "missing_clauses": "Not applicable.",
        }
        assert post_analyze(client, ai).status_code == 503


# ---------------------------------------------------------------------------
# 6. Malformed AI JSON -> 503, no persistence
# ---------------------------------------------------------------------------

class TestMalformedAIOutput:
    def test_malformed_json_returns_503(self, client):
        with patch('app.get_gemini_response', return_value="This is not JSON at all."), \
             patch('app.extract_text_from_file', return_value="Valid document text long enough to pass."):
            data = {
                'language': 'English',
                'tags': 'test',
                'document': (io.BytesIO(b"dummy"), "malformed.pdf"),
            }
            resp = client.post('/analyze', data=data, content_type='multipart/form-data')
        assert resp.status_code == 503
        assert "error" in resp.get_json()

    def test_null_ai_response_returns_503(self, client):
        with patch('app.get_gemini_response', return_value=None), \
             patch('app.extract_text_from_file', return_value="Valid document text long enough to pass."):
            data = {
                'language': 'English',
                'tags': 'test',
                'document': (io.BytesIO(b"dummy"), "null_ai.pdf"),
            }
            resp = client.post('/analyze', data=data, content_type='multipart/form-data')
        assert resp.status_code == 503

    def test_503_does_not_persist_record(self, client):
        filename = "no_persist_class.pdf"
        with patch('app.get_gemini_response', return_value=None), \
             patch('app.extract_text_from_file', return_value="Valid document text long enough to pass."):
            data = {
                'language': 'English',
                'tags': 'test',
                'document': (io.BytesIO(b"dummy"), filename),
            }
            client.post('/analyze', data=data, content_type='multipart/form-data')
        count = DocumentRepository.collection().count_documents({"filename": filename})
        assert count == 0, "No documents must be persisted when AI fails"


# ---------------------------------------------------------------------------
# 7. Fairness score validation
# ---------------------------------------------------------------------------

class TestFairnessScoreValidation:
    def test_contract_out_of_range_score_is_rejected(self, client):
        ai = {
            "doc_category": "contract",
            "doc_type": "Loan Agreement",
            "detected_jurisdiction": "General",
            "sentiment": "Neutral",
            "key_info": {
                "readability_score": 5,
                "fairness_score": 15,   # out of range
                "score_justification": "Score should be clipped.",
                "parties": "Borrower & Lender",
                "financial_terms": "$10,000 at 5% p.a.",
                "tenure": "2 years",
            },
            "summary_and_checklist": "Loan summary.",
            "risk_analysis": "High-interest risk.",
            "questions_to_ask": "Can rate be reduced?",
            "legal_formalities_guidance": "Stamp duty required.",
            "missing_clauses": "Prepayment clause absent.",
        }
        resp = post_analyze(client, ai)
        assert resp.status_code == 503

    def test_contract_non_numeric_score_is_rejected(self, client):
        ai = {
            "doc_category": "contract",
            "doc_type": "Service Agreement",
            "detected_jurisdiction": "General",
            "sentiment": "Neutral",
            "key_info": {
                "readability_score": 6,
                "fairness_score": "moderate",  # non-numeric
                "score_justification": "Non-numeric score.",
                "parties": "Client & Vendor",
                "financial_terms": "$5,000/month",
                "tenure": "1 year",
            },
            "summary_and_checklist": "Service summary.",
            "risk_analysis": "Risk items.",
            "questions_to_ask": "Questions.",
            "legal_formalities_guidance": "Guidance.",
            "missing_clauses": "Missing.",
        }
        resp = post_analyze(client, ai)
        assert resp.status_code == 503

    def test_missing_required_analysis_field_is_rejected_without_persistence(self, client):
        incomplete = {
            "doc_category": "other",
            "doc_type": "Invoice",
            "detected_jurisdiction": "Not applicable",
            "sentiment": "Neutral",
            "key_info": {"readability_score": 5},
            "summary_and_checklist": "Invoice summary.",
            "risk_analysis": "No notable caveats.",
            "questions_to_ask": "What is the payment due date?",
            "legal_formalities_guidance": "Not applicable.",
        }
        response = post_analyze(client, incomplete)
        assert response.status_code == 503

    def test_non_contract_numeric_score_always_null(self, client):
        """Even if the AI erroneously returns a numeric score for a non-contract,
        the backend must override it to None."""
        ai = {
            "doc_category": "academic_informational",
            "doc_type": "Textbook Chapter",
            "detected_jurisdiction": "Not applicable",
            "sentiment": "Informational",
            "key_info": {
                "readability_score": 8,
                "fairness_score": 7,   # AI erroneously returned a score
                "score_justification": "Should be overridden to null by backend.",
                "subject": "Database Systems",
                "document_scope": "Introduction to SQL.",
                "source_type": "Textbook Chapter",
            },
            "summary_and_checklist": "Covers SQL basics.",
            "risk_analysis": "No significant caveats.",
            "questions_to_ask": "What is a JOIN?",
            "legal_formalities_guidance": "Not applicable.",
            "missing_clauses": "Not applicable.",
        }
        resp = post_analyze(client, ai)
        assert resp.status_code == 200
        score = resp.get_json()["key_info"].get("fairness_score")
        assert score is None, f"Academic doc must have null fairness_score even if AI returned {score}"


# ---------------------------------------------------------------------------
# 8. MongoDB persistence and sharing remain operational
# ---------------------------------------------------------------------------

class TestPersistenceAndSharingStillWork:
    ACADEMIC_AI = {
        "doc_category": "academic_informational",
        "doc_type": "Lecture Notes",
        "detected_jurisdiction": "Not applicable",
        "sentiment": "Informational",
        "key_info": {
            "readability_score": 8,
            "fairness_score": None,
            "score_justification": "Not applicable - this is not a legal contract",
            "subject": "Project Management",
            "document_scope": "SDLC and estimation.",
            "source_type": "Lecture Notes",
        },
        "summary_and_checklist": "Key PM concepts.",
        "risk_analysis": "Minor: simplified treatment.",
        "questions_to_ask": "What is a Gantt chart?",
        "legal_formalities_guidance": "Not applicable.",
        "missing_clauses": "Not applicable.",
    }

    def test_academic_analysis_can_be_shared(self, client):
        """Share link creation must work for academic documents."""
        resp = post_analyze(client, self.ACADEMIC_AI)
        assert resp.status_code == 200
        doc_id = resp.get_json()["doc_id"]

        share_resp = client.post('/create_share_link', json={"doc_id": doc_id})
        assert share_resp.status_code == 200
        share_id = share_resp.get_json()["share_id"]

        get_resp = client.get(f'/get_shared_analysis/{share_id}')
        assert get_resp.status_code == 200
        shared = get_resp.get_json()
        assert shared["doc_type"] == "Lecture Notes"

    def test_history_includes_academic_analyses(self, client):
        """The /api/history route must return academic analyses."""
        resp = post_analyze(client, self.ACADEMIC_AI)
        assert resp.status_code == 200

        history_resp = client.get('/api/history')
        assert history_resp.status_code == 200
        analyses = history_resp.get_json()["analyses"]
        assert any(a.get("doc_category") == "academic_informational" for a in analyses)


# ---------------------------------------------------------------------------
# 9. Gemini retry / timeout / failure-handling preserved
# ---------------------------------------------------------------------------

class TestGeminiReliabilityPreserved:
    def test_transient_error_triggers_fallback(self):
        """Verify that a 503 on the primary triggers fallback - unchanged behaviour."""
        from app import get_gemini_response, PRIMARY_GEMINI_MODEL, FALLBACK_GEMINI_MODEL

        mock_client = MagicMock()
        primary_err = Exception("503 Service Unavailable")
        setattr(primary_err, 'code', 503)

        mock_fallback_res = MagicMock()
        mock_fallback_res.text = (
            '{"doc_category":"contract","doc_type":"Test","detected_jurisdiction":"India",'
            '"sentiment":"Neutral","key_info":{"readability_score":7,"fairness_score":6,'
            '"score_justification":"Test","parties":"A & B","financial_terms":"$100",'
            '"tenure":"1yr"},"summary_and_checklist":"Summary.",'
            '"risk_analysis":"Risks.","questions_to_ask":"Q.",'
            '"legal_formalities_guidance":"Stamp duty.","missing_clauses":"None."}'
        )

        def mock_generate(model, contents):
            if model == PRIMARY_GEMINI_MODEL:
                raise primary_err
            return mock_fallback_res

        mock_client.models.generate_content.side_effect = mock_generate

        with patch('google.genai.Client', return_value=mock_client), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            result = get_gemini_response("Test prompt")
            assert result is not None
            assert "doc_category" in result

    def test_permanent_error_aborts_without_retry(self):
        """A 401 on primary must abort immediately - unchanged behaviour."""
        from app import get_gemini_response

        mock_client = MagicMock()
        permanent_err = Exception("401 API_KEY_INVALID")
        setattr(permanent_err, 'code', 401)
        mock_client.models.generate_content.side_effect = permanent_err

        with patch('google.genai.Client', return_value=mock_client), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "invalid_key"}):
            result = get_gemini_response("Test prompt")
            assert result is None
            assert mock_client.models.generate_content.call_count == 1

    def test_primary_timeout_uses_fallback_model(self):
        """A primary timeout retains the bounded fallback behavior."""
        from app import get_gemini_response, PRIMARY_GEMINI_MODEL, FALLBACK_GEMINI_MODEL

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"doc_category":"other"}'

        def model_call(client, model_name, prompt, timeout_seconds=14.0):
            if model_name == PRIMARY_GEMINI_MODEL:
                raise TimeoutError("primary model timed out")
            assert model_name == FALLBACK_GEMINI_MODEL
            return mock_response

        with patch('google.genai.Client', return_value=mock_client), \
             patch('app._call_model_with_bounded_timeout', side_effect=model_call), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            assert get_gemini_response("Test prompt") == '{"doc_category":"other"}'
