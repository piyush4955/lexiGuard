"""
LexiGuard MongoDB Atlas Database Layer
Provides reliable connection management, connection verification,
safe error handling, and structured data access operations.
"""

import os
import re
import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError as PyMongoConfigError, ServerSelectionTimeoutError
from bson import ObjectId

# Load environment variables
load_dotenv()


class DatabaseConfigurationError(Exception):
    """Raised when database configuration is missing or invalid."""
    pass


class DatabaseConnectionError(Exception):
    """Raised when connecting to MongoDB fails or times out."""
    pass


def sanitize_uri(uri: Optional[str]) -> str:
    """Removes credentials from a MongoDB URI for safe logging and error messages."""
    if not uri:
        return "<EMPTY_URI>"
    # Replace username:password in mongodb(+srv)://username:password@host
    return re.sub(r'(mongodb(\+srv)?://)([^:]+):([^@]+)@', r'\1***:***@', uri)


def sanitize_error_message(message: str) -> str:
    """Sanitizes any potential connection strings or credentials from exception messages."""
    if not message:
        return ""
    return re.sub(r'(mongodb(\+srv)?://)([^:]+):([^@]+)@', r'\1***:***@', str(message))


class MongoDBManager:
    """
    Manages MongoDB client lifecycle, database references, and health checks.
    Ensures a single MongoClient instance across the application lifecycle.
    """

    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None

    @classmethod
    def get_config(cls) -> Dict[str, str]:
        """Reads and validates MongoDB configuration from environment."""
        load_dotenv()
        uri = os.getenv("MONGODB_URI", "").strip()
        db_name = os.getenv("MONGODB_DATABASE", "lexiguard").strip()

        if not uri:
            raise DatabaseConfigurationError(
                "Missing required environment variable 'MONGODB_URI'. "
                "Please configure your MongoDB Atlas SRV URI in backend/.env"
            )
        if not db_name:
            raise DatabaseConfigurationError(
                "Missing required environment variable 'MONGODB_DATABASE'. "
                "Please set MONGODB_DATABASE=lexiguard in backend/.env"
            )

        return {"uri": uri, "db_name": db_name}

    @classmethod
    def get_client(cls, timeout_ms: int = 5000) -> MongoClient:
        """
        Returns the active MongoClient singleton or initializes a new one.
        Uses sensible timeouts to prevent hanging on network failure.
        """
        if cls._client is None:
            config = cls.get_config()
            try:
                cls._client = MongoClient(
                    config["uri"],
                    serverSelectionTimeoutMS=timeout_ms,
                    connectTimeoutMS=timeout_ms,
                    socketTimeoutMS=10000,
                    appname="LexiGuard"
                )
            except (PyMongoConfigError, Exception) as e:
                cls._client = None
                safe_err = sanitize_error_message(str(e))
                raise DatabaseConnectionError(f"Failed to initialize MongoDB client: {safe_err}")

        return cls._client

    @classmethod
    def get_database(cls) -> Database:
        """Returns the configured application database instance."""
        if cls._db is None:
            client = cls.get_client()
            config = cls.get_config()
            cls._db = client[config["db_name"]]
        return cls._db

    @classmethod
    def verify_connection(cls, timeout_ms: int = 5000) -> Dict[str, Any]:
        """
        Verifies connectivity by executing a lightweight ping command on the cluster.
        Returns connection details if successful, raises DatabaseConnectionError on failure.
        """
        config = cls.get_config()
        try:
            client = cls.get_client(timeout_ms=timeout_ms)
            # Execute ping command against the admin database
            ping_result = client.admin.command('ping')
            return {
                "status": "connected",
                "database": config["db_name"],
                "ping": ping_result.get("ok", 1) == 1
            }
        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            safe_err = sanitize_error_message(str(e))
            raise DatabaseConnectionError(
                f"Could not connect to MongoDB Atlas cluster within {timeout_ms}ms timeout. "
                "Check cluster status, network/IP access list, and credentials."
            )
        except Exception as e:
            safe_err = sanitize_error_message(str(e))
            raise DatabaseConnectionError(f"Database verification failed: {safe_err}")

    @classmethod
    def close(cls) -> None:
        """Closes the MongoDB client connection cleanly."""
        if cls._client is not None:
            try:
                cls._client.close()
            finally:
                cls._client = None
                cls._db = None


def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively formats MongoDB documents for JSON serialization."""
    if doc is None:
        return None
    res = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, datetime.datetime):
            res[k] = v.isoformat()
        elif isinstance(v, dict):
            res[k] = serialize_doc(v)
        elif isinstance(v, list):
            res[k] = [
                serialize_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, datetime.datetime)
                else item
                for item in v
            ]
        else:
            res[k] = v
    return res


# --- REPOSITORY LAYER ---

class DocumentRepository:
    """Data access methods for the 'documents' collection."""

    @staticmethod
    def collection():
        return MongoDBManager.get_database()["documents"]

    @classmethod
    def insert_document(cls, doc_data: Dict[str, Any]) -> str:
        """Inserts a new document record. Returns the doc_id."""
        if "created_at" not in doc_data:
            doc_data["created_at"] = datetime.datetime.now(datetime.timezone.utc)
        result = cls.collection().insert_one(doc_data)
        return str(result.inserted_id)

    @classmethod
    def find_by_doc_id(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        """Finds a document record by application UUID doc_id."""
        doc = cls.collection().find_one({"doc_id": doc_id})
        return serialize_doc(doc)


class AnalysisRepository:
    """Data access methods for the 'analyses' collection."""

    @staticmethod
    def collection():
        return MongoDBManager.get_database()["analyses"]

    @classmethod
    def insert_analysis(cls, analysis_data: Dict[str, Any]) -> str:
        """Inserts an analysis record. Returns the inserted _id string."""
        if "created_at" not in analysis_data:
            analysis_data["created_at"] = datetime.datetime.now(datetime.timezone.utc)
        result = cls.collection().insert_one(analysis_data)
        return str(result.inserted_id)

    @classmethod
    def find_by_doc_id(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        """Finds analysis by doc_id."""
        doc = cls.collection().find_one({"doc_id": doc_id})
        return serialize_doc(doc)

    @classmethod
    def list_recent(cls, limit: int = 20, skip: int = 0) -> List[Dict[str, Any]]:
        """Lists recent analyses sorted by creation date descending."""
        cursor = cls.collection().find().sort("created_at", -1).skip(skip).limit(limit)
        return [serialize_doc(doc) for doc in cursor]


class SharedAnalysisRepository:
    """Data access methods for the 'shared_analyses' collection."""

    @staticmethod
    def collection():
        return MongoDBManager.get_database()["shared_analyses"]

    @classmethod
    def insert_share(cls, share_data: Dict[str, Any]) -> str:
        """Inserts a share record. Returns the inserted _id string."""
        if "created_at" not in share_data:
            share_data["created_at"] = datetime.datetime.now(datetime.timezone.utc)
        result = cls.collection().insert_one(share_data)
        return str(result.inserted_id)

    @classmethod
    def find_by_share_id(cls, share_id: str) -> Optional[Dict[str, Any]]:
        """Finds a share record by share_id token."""
        doc = cls.collection().find_one({"share_id": share_id, "is_revoked": {"$ne": True}})
        return serialize_doc(doc)


def init_indexes():
    """Ensures necessary indexes on collections."""
    db = MongoDBManager.get_database()
    # documents collection indexes
    db["documents"].create_index("doc_id", unique=True)
    db["documents"].create_index([("created_at", -1)])
    db["documents"].create_index([("user_id", 1), ("created_at", -1)])

    # analyses collection indexes
    db["analyses"].create_index("doc_id")
    db["analyses"].create_index([("created_at", -1)])
    db["analyses"].create_index("tags")

    # shared_analyses collection indexes
    db["shared_analyses"].create_index("share_id", unique=True)
    db["shared_analyses"].create_index([("created_at", -1)])
