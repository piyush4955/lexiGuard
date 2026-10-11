"""
Unit tests for LexiGuard MongoDB Atlas Connection Manager and Configuration Layer.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from db import (
    MongoDBManager,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    sanitize_uri,
    sanitize_error_message,
    serialize_doc,
)
from bson import ObjectId
import datetime


class TestMongoDBConfiguration:
    """Tests environment variable loading and validation."""

    def test_missing_mongodb_uri_raises_config_error(self):
        with patch.dict(os.environ, {"MONGODB_URI": "", "MONGODB_DATABASE": "lexiguard"}, clear=False):
            MongoDBManager.close()
            with pytest.raises(DatabaseConfigurationError) as exc_info:
                MongoDBManager.get_config()
            assert "Missing required environment variable 'MONGODB_URI'" in str(exc_info.value)

    def test_missing_mongodb_database_raises_config_error(self):
        with patch.dict(os.environ, {"MONGODB_URI": "mongodb://localhost:27017", "MONGODB_DATABASE": ""}, clear=False):
            MongoDBManager.close()
            with pytest.raises(DatabaseConfigurationError) as exc_info:
                MongoDBManager.get_config()
            assert "Missing required environment variable 'MONGODB_DATABASE'" in str(exc_info.value)

    def test_valid_config_returned(self):
        test_uri = "mongodb+srv://user:pass@lexiguard-cluster.aofcopa.mongodb.net"
        with patch.dict(os.environ, {"MONGODB_URI": test_uri, "MONGODB_DATABASE": "lexiguard"}, clear=False):
            config = MongoDBManager.get_config()
            assert config["uri"] == test_uri
            assert config["db_name"] == "lexiguard"


class TestSecretSanitization:
    """Verifies credentials and connection strings are scrubbed from logs and errors."""

    def test_sanitize_uri_redacts_credentials(self):
        raw_uri = "mongodb+srv://admin_user:SuperSecretPassword123@lexiguard-cluster.aofcopa.mongodb.net/lexiguard"
        sanitized = sanitize_uri(raw_uri)
        assert "SuperSecretPassword123" not in sanitized
        assert "admin_user" not in sanitized
        assert "***:***@" in sanitized

    def test_sanitize_error_message_redacts_credentials(self):
        raw_msg = "Connection failed to mongodb+srv://app_user:MySecretPass@cluster0.mongodb.net: Server selection timeout"
        sanitized = sanitize_error_message(raw_msg)
        assert "MySecretPass" not in sanitized
        assert "app_user" not in sanitized
        assert "mongodb+srv://***:***@cluster0.mongodb.net" in sanitized


class TestConnectionVerificationAndTimeout:
    """Verifies timeout behavior and connectivity verification."""

    def test_unreachable_endpoint_fails_fast_with_timeout(self):
        """Points to a non-routable IP to verify serverSelectionTimeoutMS fails within timeout without hanging."""
        unreachable_uri = "mongodb://192.0.2.1:27017/?serverSelectionTimeoutMS=500"
        with patch.dict(os.environ, {"MONGODB_URI": unreachable_uri, "MONGODB_DATABASE": "lexiguard"}, clear=False):
            MongoDBManager.close()
            with pytest.raises(DatabaseConnectionError) as exc_info:
                MongoDBManager.verify_connection(timeout_ms=500)
            assert "Could not connect to MongoDB Atlas" in str(exc_info.value)
            MongoDBManager.close()

    def test_verify_connection_succeeds_with_mock_client(self):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1.0}

        with patch.object(MongoDBManager, 'get_client', return_value=mock_client), \
             patch.dict(os.environ, {"MONGODB_URI": "mongodb://localhost:27017", "MONGODB_DATABASE": "lexiguard"}):
            res = MongoDBManager.verify_connection()
            assert res["status"] == "connected"
            assert res["database"] == "lexiguard"
            assert res["ping"] is True


class TestSerialization:
    """Verifies document serialization for JSON safety."""

    def test_serialize_doc_converts_objectid_and_datetime(self):
        oid = ObjectId()
        now = datetime.datetime.now(datetime.timezone.utc)
        raw_doc = {
            "_id": oid,
            "doc_id": "test-uuid-123",
            "created_at": now,
            "nested": {
                "id": oid,
                "timestamp": now
            },
            "array": [oid, now, "simple_string"]
        }
        serialized = serialize_doc(raw_doc)
        assert serialized["_id"] == str(oid)
        assert serialized["created_at"] == now.isoformat()
        assert serialized["nested"]["id"] == str(oid)
        assert serialized["nested"]["timestamp"] == now.isoformat()
        assert serialized["array"][0] == str(oid)
        assert serialized["array"][1] == now.isoformat()
        assert serialized["array"][2] == "simple_string"

    def test_serialize_none_returns_none(self):
        assert serialize_doc(None) is None
