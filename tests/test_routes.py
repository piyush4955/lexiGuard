"""
Integration tests for LexiGuard Flask routes with MongoDB persistence.
"""

import os
import sys
import pytest
import mongomock
from unittest.mock import patch, MagicMock
import io
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app import app
import app as app_module
from db import MongoDBManager, DocumentRepository, AnalysisRepository, SharedAnalysisRepository, init_indexes


@pytest.fixture
def client():
    """Sets up Flask test client with an isolated in-memory mongomock database."""
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


class TestAnalyzeRoute:
    def test_analyze_persists_to_mongodb_and_returns_expected_schema(self, client):
        mock_ai_json = {
            "doc_category": "contract",
            "doc_type": "Rental Agreement",
            "detected_jurisdiction": "Bangalore, India",
            "sentiment": "Neutral",
            "key_info": {
                "readability_score": 8,
                "fairness_score": 7,
                "score_justification": "Standard terms.",
                "parties": "Landlord & Tenant",
                "rent_and_deposit": "Rent: 35k, Deposit: 2L",
                "tenure": "11 Months"
            },
            "summary_and_checklist": "### Summary\n- 11 month tenancy.",
            "risk_analysis": "### Risks\n- Short notice eviction.",
            "questions_to_ask": "Notice period?",
            "legal_formalities_guidance": "Stamp duty guidance.",
            "missing_clauses": "Maintenance cap."
        }

        with patch('app.get_gemini_response', return_value=json.dumps(mock_ai_json)), \
             patch('app.extract_text_from_file', return_value="This is a valid long rental agreement text with more than thirty characters."):
            data = {
                'language': 'English',
                'tags': 'rental, lease'
            }
            # Upload a small test file
            data['document'] = (io.BytesIO(b"dummy pdf bytes"), "test_lease.pdf")
            response = client.post('/analyze', data=data, content_type='multipart/form-data')

            assert response.status_code == 200
            res_json = response.get_json()
            assert "doc_id" in res_json
            assert "key_info" in res_json
            assert "summary_and_checklist" in res_json
            assert "risk_analysis" in res_json
            assert "questions_to_ask" in res_json
            assert "legal_formalities_guidance" in res_json
            assert "missing_clauses" in res_json

            doc_id = res_json["doc_id"]

            # Verify saved in MongoDB 'documents' collection
            doc_rec = DocumentRepository.find_by_doc_id(doc_id)
            assert doc_rec is not None
            assert doc_rec["filename"] == "test_lease.pdf"

            # Verify saved in MongoDB 'analyses' collection
            analysis_rec = AnalysisRepository.find_by_doc_id(doc_id)
            assert analysis_rec is not None
            assert analysis_rec["doc_type"] == "Rental Agreement"
            assert "rental" in analysis_rec["tags"]


    def test_analyze_ai_failure_returns_503_and_does_not_persist(self, client):
        """Verifies that an AI failure in /analyze returns 503 and does NOT persist fabricated records."""
        with patch('app.get_gemini_response', return_value=None), \
             patch('app.extract_text_from_file', return_value="This is a valid long rental agreement text with more than thirty characters."):
            data = {
                'language': 'English',
                'tags': 'rental, test'
            }
            data['document'] = (io.BytesIO(b"dummy pdf bytes"), "test_lease_fail.pdf")
            response = client.post('/analyze', data=data, content_type='multipart/form-data')

            assert response.status_code == 503
            res_json = response.get_json()
            assert "error" in res_json
            assert "temporarily unavailable" in res_json["error"].lower()

            # Ensure no records were persisted in MongoDB
            docs_count = DocumentRepository.collection().count_documents({"filename": "test_lease_fail.pdf"})
            assert docs_count == 0


class TestShareRoutes:
    def test_create_and_retrieve_share_link(self, client):
        # 1. Insert a test analysis
        doc_id = "test-doc-share-123"
        AnalysisRepository.insert_analysis({
            "doc_id": doc_id,
            "filename": "Partnership_Agreement.pdf",
            "doc_type": "Partnership Deed",
            "doc_category": "contract",
            "summary_and_checklist": "50/50 profit split.",
            "risk_analysis": "Unlimited personal liability clause.",
            "questions_to_ask": "What about exit strategy?",
            "missing_clauses": "Dispute resolution.",
            "legal_formalities_guidance": "Requires stamp duty.",
            "key_info": {"parties": "A and B"}
        })

        # 2. Call /create_share_link
        resp = client.post('/create_share_link', json={"doc_id": doc_id})
        assert resp.status_code == 200
        share_json = resp.get_json()
        assert "share_id" in share_json
        share_id = share_json["share_id"]

        # 3. Call /get_shared_analysis/<share_id>
        get_resp = client.get(f'/get_shared_analysis/{share_id}')
        assert get_resp.status_code == 200
        get_json = get_resp.get_json()
        assert get_json["share_id"] == share_id
        assert get_json["filename"] == "Partnership_Agreement.pdf"
        assert get_json["doc_type"] == "Partnership Deed"
        assert get_json["doc_category"] == "contract"
        assert get_json["summary_and_checklist"] == "50/50 profit split."
        assert get_json["questions_to_ask"] == "What about exit strategy?"
        assert get_json["missing_clauses"] == "Dispute resolution."
        assert get_json["legal_formalities_guidance"] == "Requires stamp duty."
        assert get_json["key_info"] == {"parties": "A and B"}

    def test_share_nonexistent_doc_returns_404(self, client):
        resp = client.post('/create_share_link', json={"doc_id": "non-existent-id"})
        assert resp.status_code == 404

    def test_get_nonexistent_share_returns_404(self, client):
        resp = client.get('/get_shared_analysis/invalid-share-id')
        assert resp.status_code == 404


class TestHistoryAndDocumentRoutes:
    def test_get_history_returns_mongodb_analyses(self, client):
        for i in range(3):
            AnalysisRepository.insert_analysis({
                "doc_id": f"history-doc-{i}",
                "filename": f"document_{i}.pdf",
                "doc_type": "Loan Contract",
                "summary_and_checklist": f"Loan summary {i}"
            })

        resp = client.get('/api/history')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "analyses" in data
        assert len(data["analyses"]) >= 3
        assert data["source"] == "mongodb"

    def test_get_document_by_id(self, client):
        doc_id = "specific-doc-456"
        AnalysisRepository.insert_analysis({
            "doc_id": doc_id,
            "filename": "NDA.docx",
            "doc_type": "NDA",
            "summary_and_checklist": "Confidentiality terms."
        })

        resp = client.get(f'/api/document/{doc_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["doc_id"] == doc_id
        assert data["filename"] == "NDA.docx"

    def test_get_document_not_found(self, client):
        resp = client.get('/api/document/missing-id')
        assert resp.status_code == 404


class TestHealthCheckRoute:
    def test_health_check(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["mongodb_connected"] is True


class TestExistingAuxiliaryRoutes:
    def test_explain_term_success(self, client):
        with patch('app.get_gemini_response', return_value="An amount deposited to secure performance."):
            resp = client.post('/explain_term', json={"term": "security deposit", "language": "English"})
            assert resp.status_code == 200
            assert "explanation" in resp.get_json()
            assert resp.get_json()["explanation"] == "An amount deposited to secure performance."

    def test_explain_term_empty_ai_response_returns_503(self, client):
        """Verifies that empty AI output does NOT return 200 with null, but returns 503."""
        with patch('app.get_gemini_response', return_value=None):
            resp = client.post('/explain_term', json={"term": "security deposit", "language": "English"})
            assert resp.status_code == 503
            assert "error" in resp.get_json()

    def test_analyze_clause_success(self, client):
        with patch('app.get_gemini_response', return_value="This clause requires advance notice."):
            resp = client.post('/analyze_clause', json={"clause_text": "Tenant shall give 30 days notice.", "language": "English"})
            assert resp.status_code == 200
            assert "explanation" in resp.get_json()

    def test_analyze_clause_empty_ai_response_returns_503(self, client):
        """Verifies that empty clause AI output returns 503 instead of 200 with null."""
        with patch('app.get_gemini_response', return_value=None):
            resp = client.post('/analyze_clause', json={"clause_text": "Tenant shall give 30 days notice.", "language": "English"})
            assert resp.status_code == 503
            assert "error" in resp.get_json()

    def test_compare_success(self, client):
        with patch('app.get_gemini_response', return_value="Clause 4 increased rent by 10%."), \
             patch('app.extract_text_from_file', return_value="Document content text"):
            data = {
                'language': 'English',
                'doc_a': (io.BytesIO(b"old doc"), "doc_a.pdf"),
                'doc_b': (io.BytesIO(b"new doc"), "doc_b.pdf")
            }
            resp = client.post('/compare', data=data, content_type='multipart/form-data')
            assert resp.status_code == 200
            assert "comparison" in resp.get_json()
            assert resp.get_json()["comparison"] == "Clause 4 increased rent by 10%."

    def test_compare_empty_ai_response_returns_503(self, client):
        """Verifies that empty compare AI output returns 503 instead of 200 with null."""
        with patch('app.get_gemini_response', return_value=None), \
             patch('app.extract_text_from_file', return_value="Document content text"):
            data = {
                'language': 'English',
                'doc_a': (io.BytesIO(b"old doc"), "doc_a.pdf"),
                'doc_b': (io.BytesIO(b"new doc"), "doc_b.pdf")
            }
            resp = client.post('/compare', data=data, content_type='multipart/form-data')
            assert resp.status_code == 503
            assert "error" in resp.get_json()


class TestGeminiHelperFallbackAndErrors:
    """Verifies get_gemini_response fallback and selective retry logic."""

    def test_gemini_transient_error_retries_with_fallback(self):
        """Primary model raises 503; fallback model succeeds."""
        from app import get_gemini_response, PRIMARY_GEMINI_MODEL, FALLBACK_GEMINI_MODEL

        mock_client = MagicMock()
        primary_err = Exception("503 Service Unavailable")
        setattr(primary_err, 'code', 503)

        mock_fallback_res = MagicMock()
        mock_fallback_res.text = "Fallback success explanation."

        def mock_generate(model, contents):
            if model == PRIMARY_GEMINI_MODEL:
                raise primary_err
            elif model == FALLBACK_GEMINI_MODEL:
                return mock_fallback_res
            raise Exception("Unexpected model")

        mock_client.models.generate_content.side_effect = mock_generate

        with patch('google.genai.Client', return_value=mock_client), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test_api_key"}):
            result = get_gemini_response("Test prompt")
            assert result == "Fallback success explanation."
            # Verify primary was called first, then fallback
            assert mock_client.models.generate_content.call_count == 2

    def test_gemini_permanent_error_aborts_immediately(self):
        """Primary model raises 401 Invalid API Key; aborts immediately without retrying fallback."""
        from app import get_gemini_response

        mock_client = MagicMock()
        permanent_err = Exception("401 API_KEY_INVALID")
        setattr(permanent_err, 'code', 401)

        mock_client.models.generate_content.side_effect = permanent_err

        with patch('google.genai.Client', return_value=mock_client), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "invalid_key"}):
            result = get_gemini_response("Test prompt")
            assert result is None
            # Aborted after 1 attempt, did not retry
            assert mock_client.models.generate_content.call_count == 1


class TestDeploymentAndCORS:
    def test_health_check_endpoint(self, client):
        """Verify /api/health returns healthy without leaking secrets."""
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'healthy'
        assert 'mongodb_connected' in data
        assert 'firebase_connected' in data
        assert 'gemini_configured' in data
        # Ensure no credential keys are leaked
        assert 'GEMINI_API_KEY' not in data
        assert 'MONGODB_URI' not in data

    def test_cors_options_preflight_allowed_origin(self, client):
        """Verify CORS preflight returns 200 and access-control headers for allowed origins."""
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type,Authorization'
        }
        resp = client.options('/analyze', headers=headers)
        assert resp.status_code in (200, 204)
        assert resp.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'

    def test_cors_options_preflight_production_vercel_origin(self, client):
        """Verify preflight specifically allows the deployed Vercel frontend origin with expected headers."""
        headers = {
            'Origin': 'https://lexiguard-frontend-eta.vercel.app',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type'
        }
        resp = client.options('/analyze', headers=headers)
        assert resp.status_code in (200, 204)
        assert resp.headers.get('Access-Control-Allow-Origin') == 'https://lexiguard-frontend-eta.vercel.app'
        assert resp.headers.get('Access-Control-Allow-Credentials') == 'true'
        assert 'POST' in resp.headers.get('Access-Control-Allow-Methods', '')
        allow_headers = resp.headers.get('Access-Control-Allow-Headers', '').lower()
        assert 'authorization' in allow_headers
        assert 'content-type' in allow_headers

    def test_cors_disallows_unauthorized_origin(self, client):
        """Verify disallowed origins do not receive Access-Control-Allow-Origin headers."""
        headers = {
            'Origin': 'https://unauthorized-attacker-site.com',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type'
        }
        resp = client.options('/analyze', headers=headers)
        assert resp.status_code == 200
        assert 'Access-Control-Allow-Origin' not in resp.headers

