"""
Unit and integration tests for LexiGuard MongoDB Schema, CRUD operations,
indexes, and data persistence across client restarts.
"""

import os
import sys
import pytest
import mongomock
from unittest.mock import patch
import datetime
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from db import (
    MongoDBManager,
    DocumentRepository,
    AnalysisRepository,
    SharedAnalysisRepository,
    init_indexes,
    serialize_doc
)


@pytest.fixture(autouse=True)
def mock_mongo():
    """Sets up an isolated in-memory mongomock database for each test."""
    mock_client = mongomock.MongoClient()
    with patch.object(MongoDBManager, 'get_client', return_value=mock_client), \
         patch.object(MongoDBManager, 'get_database', return_value=mock_client["lexiguard"]), \
         patch.dict(os.environ, {"MONGODB_URI": "mongodb://localhost:27017", "MONGODB_DATABASE": "lexiguard"}):
        MongoDBManager._client = mock_client
        MongoDBManager._db = mock_client["lexiguard"]
        init_indexes()
        yield mock_client
        MongoDBManager._client = None
        MongoDBManager._db = None


class TestDocumentRepository:
    def test_insert_and_find_document(self):
        doc_id = str(uuid.uuid4())
        doc_meta = {
            "doc_id": doc_id,
            "filename": "Lease_Agreement.pdf",
            "file_type": ".pdf",
            "file_size": 20480,
            "source": "upload",
            "status": "processed",
            "user_id": "guest_user"
        }
        inserted_id = DocumentRepository.insert_document(doc_meta)
        assert inserted_id is not None

        found = DocumentRepository.find_by_doc_id(doc_id)
        assert found is not None
        assert found["doc_id"] == doc_id
        assert found["filename"] == "Lease_Agreement.pdf"
        assert found["file_type"] == ".pdf"
        assert found["file_size"] == 20480
        assert found["status"] == "processed"
        assert "created_at" in found

    def test_find_nonexistent_document_returns_none(self):
        result = DocumentRepository.find_by_doc_id("non-existent-uuid")
        assert result is None


class TestAnalysisRepository:
    def test_insert_and_find_analysis(self):
        doc_id = str(uuid.uuid4())
        analysis_data = {
            "doc_id": doc_id,
            "filename": "Lease_Agreement.pdf",
            "doc_type": "Rental Agreement",
            "language": "English",
            "jurisdiction": "Bangalore, India",
            "key_info": {
                "fairness_score": 7,
                "readability_score": 8,
                "parties": "Landlord & Tenant"
            },
            "summary_and_checklist": "### Summary\n- Key lease terms.",
            "risk_analysis": "### Risk Radar\n- 6 month lock-in penalty.",
            "questions_to_ask": "1. Can penalty be reduced?",
            "legal_formalities_guidance": "Stamp duty applicable.",
            "missing_clauses": "Force majeure.",
            "tags": ["rental", "bangalore"],
            "user_id": "guest_user"
        }
        inserted_id = AnalysisRepository.insert_analysis(analysis_data)
        assert inserted_id is not None

        found = AnalysisRepository.find_by_doc_id(doc_id)
        assert found is not None
        assert found["doc_id"] == doc_id
        assert found["doc_type"] == "Rental Agreement"
        assert found["key_info"]["fairness_score"] == 7
        assert "rental" in found["tags"]

    def test_list_recent_analyses(self):
        for i in range(5):
            doc_id = f"doc-id-{i}"
            AnalysisRepository.insert_analysis({
                "doc_id": doc_id,
                "filename": f"contract_{i}.pdf",
                "doc_type": "Employment Agreement",
                "summary_and_checklist": f"Summary {i}",
                "created_at": datetime.datetime.now(datetime.timezone.utc)
            })

        recent = AnalysisRepository.list_recent(limit=3)
        assert len(recent) == 3


class TestSharedAnalysisRepository:
    def test_insert_and_find_share(self):
        share_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        share_data = {
            "share_id": share_id,
            "doc_id": doc_id,
            "filename": "NDA.pdf",
            "doc_type": "Non-Disclosure Agreement",
            "summary_and_checklist": "Standard mutual NDA summary.",
            "risk_analysis": "Strict confidentiality clauses.",
            "is_revoked": False
        }
        inserted_id = SharedAnalysisRepository.insert_share(share_data)
        assert inserted_id is not None

        retrieved = SharedAnalysisRepository.find_by_share_id(share_id)
        assert retrieved is not None
        assert retrieved["share_id"] == share_id
        assert retrieved["filename"] == "NDA.pdf"
        assert retrieved["doc_type"] == "Non-Disclosure Agreement"

    def test_revoked_share_returns_none(self):
        share_id = str(uuid.uuid4())
        SharedAnalysisRepository.insert_share({
            "share_id": share_id,
            "doc_id": "doc-revoked",
            "is_revoked": True
        })
        retrieved = SharedAnalysisRepository.find_by_share_id(share_id)
        assert retrieved is None


class TestPersistenceAcrossRestart:
    """Verifies data persists across client close and re-initialization."""

    def test_data_durability_across_reconnect(self):
        mock_server = mongomock.MongoClient()
        db_first_session = mock_server["lexiguard"]

        # First connection session
        with patch.object(MongoDBManager, 'get_database', return_value=db_first_session):
            doc_id = "persistent-doc-001"
            DocumentRepository.insert_document({
                "doc_id": doc_id,
                "filename": "Persistent_Contract.pdf",
                "status": "processed"
            })
            AnalysisRepository.insert_analysis({
                "doc_id": doc_id,
                "doc_type": "Commercial Lease",
                "summary_and_checklist": "Verified persistent record."
            })

        # Simulate full client shutdown & cleanup
        MongoDBManager.close()

        # Second connection session against the same database cluster
        db_second_session = mock_server["lexiguard"]
        with patch.object(MongoDBManager, 'get_database', return_value=db_second_session):
            doc = DocumentRepository.find_by_doc_id(doc_id)
            analysis = AnalysisRepository.find_by_doc_id(doc_id)

            assert doc is not None
            assert doc["filename"] == "Persistent_Contract.pdf"
            assert analysis is not None
            assert analysis["doc_type"] == "Commercial Lease"
