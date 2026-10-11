import sys
sys.modules['google._upb._message'] = None
sys.modules['google._upb'] = None

import os
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

import pkgutil
import importlib.util
if not hasattr(pkgutil, 'find_loader'):
    pkgutil.find_loader = lambda name: importlib.util.find_spec(name)

import datetime
import uuid
import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import pdfplumber
try:
    import pytesseract
except Exception as e:
    print(f"Warning: pytesseract import fallback: {e}")
    pytesseract = None
from PIL import Image
import io
import docx

# Firebase Admin imports
try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
except Exception as e:
    print(f"Notice: Firebase Admin import fallback: {e}")
    firebase_admin = None
    credentials = None
    auth = None
    firestore = None

# MongoDB Atlas Database Layer
from db import (
    MongoDBManager,
    DocumentRepository,
    AnalysisRepository,
    SharedAnalysisRepository,
    init_indexes,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    sanitize_error_message
)

# --- INITIALIZATION ---
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    load_dotenv(_env_path)
else:
    load_dotenv()

USE_MONGODB = False
mongo_status_msg = "Not initialized"

def init_mongo_connection():
    global USE_MONGODB, mongo_status_msg
    try:
        MongoDBManager.verify_connection()
        init_indexes()
        USE_MONGODB = True
        mongo_status_msg = "Connected"
        print("MongoDB Atlas connected and initialized successfully.")
    except DatabaseConfigurationError as e:
        USE_MONGODB = False
        mongo_status_msg = str(e)
        print(f"Notice: MongoDB not configured ({e}).")
    except DatabaseConnectionError as e:
        USE_MONGODB = False
        mongo_status_msg = str(e)
        print(f"Warning: MongoDB connection failed ({e}).")
    except Exception as e:
        USE_MONGODB = False
        safe_msg = sanitize_error_message(str(e))
        mongo_status_msg = safe_msg
        print(f"Warning: MongoDB initialization error: {safe_msg}")

init_mongo_connection()

USE_FIREBASE = False
db = None

if firebase_admin and os.path.exists("serviceAccountKey.json"):
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIREBASE = True
        print("Firebase Admin initialized successfully.")
    except Exception as e:
        print(f"Warning: Firebase Admin initialization failed: {e}. Falling back to in-memory store.")
else:
    print("Notice: serviceAccountKey.json not found or Firebase Admin disabled. Running in MongoDB / in-memory mode.")

# In-memory storage fallback when persistent databases are not configured
in_memory_docs = {}
in_memory_shared = {}

app = Flask(__name__, static_folder='../frontend', static_url_path='')

# --- CORS CONFIGURATION ---
frontend_url_env = os.environ.get("FRONTEND_URL", "").strip()
if frontend_url_env:
    allowed_origins = [u.strip().rstrip("/") for u in frontend_url_env.split(",") if u.strip()]
    # If in local debug mode, also permit local frontend origins
    if os.environ.get("FLASK_DEBUG", "").lower() in ("true", "1", "t") or os.environ.get("FLASK_ENV") == "development":
        for d in ["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500", "http://127.0.0.1:5500"]:
            if d not in allowed_origins:
                allowed_origins.append(d)
else:
    # Default local development origins
    allowed_origins = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ]

CORS(app, origins=allowed_origins, supports_credentials=True)

# --- HELPER FUNCTIONS ---
def extract_text_from_file(file_stream, file_extension):
    """Extracts text from PDF, DOCX, and Image files, using OCR for images."""
    text = ""
    if file_extension == ".pdf":
        try:
            with pdfplumber.open(file_stream) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if len(text.strip()) < 100: # Fallback to OCR for scanned PDFs
                if pytesseract is not None:
                    try:
                        file_stream.seek(0)
                        ocr_text = ""
                        with pdfplumber.open(file_stream) as pdf:
                            for page in pdf.pages[:5]: # Cap at first 5 pages to prevent timeouts
                                im = page.to_image(resolution=200)
                                ocr_text += pytesseract.image_to_string(im.original) + "\n"
                        if ocr_text.strip():
                            text = ocr_text
                    except Exception as ocr_err:
                        print(f"Notice: PDF OCR fallback skipped ({ocr_err})")
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None
    elif file_extension in [".docx", ".doc"]:
        try:
            doc = docx.Document(file_stream)
            return '\n'.join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Error reading DOCX/DOC: {e}")
            return None
    elif file_extension in [".png", ".jpg", ".jpeg"]:
        try:
            image = Image.open(file_stream)
            if pytesseract is not None:
                text = pytesseract.image_to_string(image)
                return text
            else:
                return "Image OCR requires pytesseract and Tesseract OCR engine installed."
        except Exception as e:
            print(f"Error reading image file: {e}")
            return None
    return None

SAMPLE_RENTAL_AGREEMENT = """
RENTAL AGREEMENT
This Rent Agreement is made on 15th Day of January 2026 at Bangalore between Mr. Ramesh Kumar (Lessor/Landlord) and Ms. Ananya Sharma (Lessee/Tenant).
PROPERTY: Flat 302, Green Valley Apartments, Indiranagar, Bangalore - 560038.
TERMS AND CONDITIONS:
1. RENT & DEPOSIT: The monthly rent shall be Rs. 35,000/- payable on or before 5th of each month. The Lessee has deposited a Security Deposit of Rs. 2,00,000/- with the Lessor.
2. TENURE: The tenure of this agreement is 11 months commencing from Jan 15, 2026 to Dec 14, 2026.
3. RENT ESCALATION: Rent will automatically increase by 15% upon renewal of agreement.
4. FORFEITURE & DEDUCTIONS: In case of early termination by Lessee before 6 months lock-in period, the entire security deposit of Rs. 2,00,000 shall be forfeited. Landlord reserves the right to deduct painting charges of Rs. 25,000 regardless of tenancy duration.
5. MAINTENANCE & UTILITIES: Lessee shall pay electricity, water, and monthly maintenance fees directly to society association.
6. EVICTION: Lessor may terminate agreement with 7 days written notice in case of breach or emergency.
"""

CONSOLIDATED_ANALYSIS_PROMPT = """
You are LexiGuard AI. Your first task is to classify the uploaded document, then apply the appropriate analysis structure.

Provide ALL text responses in the {language} language.

---
STEP 1 — CLASSIFY
Read the document text and determine its category. Use ONLY one of these three values:
  - "contract": A legal agreement or other document intended to create or describe contractual obligations, including leases, loan deeds, NDAs, MOUs and service agreements.
  - "academic_informational": Lecture notes, textbook chapters, academic papers, research reports, study guides, technical documentation, or any document whose primary purpose is to inform, explain or educate rather than to create legal obligations.
  - "other": Documents that do not clearly fit either category above (e.g. invoices, forms, personal letters, resumes, images with minimal text).

If you are uncertain between "contract" and another category, prefer "academic_informational" or "other" rather than forcing a legal-contract analysis onto a non-contract document.

---
STEP 2 — ANALYZE
Return a SINGLE valid JSON object with these EXACT keys. Do NOT add extra keys.

For ALL document categories:
  - doc_category: one of the three values above (string, required)
  - doc_type: a concise human-readable document type, e.g. "Rental Agreement", "Lecture Notes — Software Project Management", "Research Paper" (string)
  - detected_jurisdiction: the jurisdiction or legal system referenced in the document (string). For non-legal documents write "Not applicable".
  - sentiment: overall sentiment or tone (string), e.g. "Neutral", "Informational", "Cautionary".
  - key_info: a JSON object of extracted metadata — see rules per category below.
  - summary_and_checklist: a markdown string with the key summary and an action checklist — see rules per category below.
  - risk_analysis: a markdown string — see rules per category below.
  - questions_to_ask: a markdown string of useful questions — see rules per category below.
  - legal_formalities_guidance: a markdown string — see rules per category below.
  - missing_clauses: a markdown string — see rules per category below.

---
RULES BY CATEGORY

If doc_category == "contract":
  key_info fields:
    - readability_score: integer 1-10
    - fairness_score: integer 1-10, based on observed imbalance of obligations. Only provide if the document contains enough content to assess; otherwise null.
    - score_justification: brief explanation of the fairness score (string)
    - parties: names of the contracting parties. If not found in the document, write "Not found in document" — do NOT write "Not applicable".
    - financial_terms: key monetary values or "Not found in document" if absent
    - tenure: contract duration or "Not found in document" if absent
  summary_and_checklist: key summary of contractual obligations followed by an action checklist for the weaker party.
  risk_analysis: ### Risk Radar & Flagged Gotchas — list genuinely problematic or one-sided clauses identified in the text. Do NOT fabricate clauses.
  questions_to_ask: negotiation prompts relevant to the actual document content.
  legal_formalities_guidance: stamp duty, registration requirements, or other formalities relevant to the detected jurisdiction. Write "Not determined — jurisdiction unclear" if jurisdiction cannot be identified.
  missing_clauses: clauses that are genuinely absent but typically expected for this document type. Base this only on what is actually missing from the provided text.

If doc_category == "academic_informational":
  key_info fields:
    - readability_score: integer 1-10
    - fairness_score: null (this field is not applicable for non-contract documents)
    - score_justification: "Not applicable — this is not a legal contract"
    - subject: the academic subject or topic
    - document_scope: brief description of what the document covers
    - source_type: e.g. "Lecture Notes", "Textbook Chapter", "Research Paper", "Technical Report"
  summary_and_checklist: ### Key Concepts\n- bullet points of main concepts\n\n### Study / Action Checklist\n- practical steps for the reader.
  risk_analysis: ### Key Caveats & Limitations\n- technical, academic, or factual limitations, assumptions, or caveats in the document. Do NOT generate contractual risk items.
  questions_to_ask: review questions or follow-up questions to deepen understanding. Do NOT generate negotiation prompts.
  legal_formalities_guidance: "Not applicable — this document is not a legal contract."
  missing_clauses: "Not applicable — this is not a contract. There are no contractual clauses to assess."

If doc_category == "other":
  key_info fields:
    - readability_score: integer 1-10
    - fairness_score: null
    - score_justification: "Not applicable — this is not a legal contract"
    - document_description: brief description of what the document appears to be
  summary_and_checklist: neutral summary of the document content.
  risk_analysis: relevant caveats or concerns specific to this document type. Do NOT generate legal contract risks if none exist.
  questions_to_ask: relevant follow-up questions for this document type.
  legal_formalities_guidance: "Not applicable — this document does not have legal formalities."
  missing_clauses: "Not applicable — this is not a contract."

---
IMPORTANT RULES (apply to ALL categories):
- Do NOT invent parties, financial figures, jurisdiction, or legal clauses that are not present in the document.
- Do NOT generate stamp duty amounts, missing clause warnings, or legal formalities for academic or informational documents.
- Distinguish "Not found in document" (information should exist but is absent) from "Not applicable" (the field does not apply to this document type).
- Return ONLY valid JSON. Do not include markdown code fences, explanation, or commentary outside the JSON object.

DOCUMENT TEXT:
"{document_text}"
"""

PRIMARY_GEMINI_MODEL = "gemini-3.5-flash"
FALLBACK_GEMINI_MODEL = "gemini-3.5-flash-lite"

def normalize_analysis_output(output):
    """Validate AI analysis structure and normalize category-specific fields."""
    if not isinstance(output, dict):
        raise ValueError("AI analysis must be a JSON object")

    valid_categories = {"contract", "academic_informational", "other"}
    doc_category = output.get("doc_category")
    if not isinstance(doc_category, str) or doc_category not in valid_categories:
        raise ValueError("AI analysis returned an unsupported document category")

    required_strings = (
        "doc_type", "detected_jurisdiction", "sentiment",
        "summary_and_checklist", "risk_analysis", "questions_to_ask",
        "legal_formalities_guidance", "missing_clauses",
    )
    for field in required_strings:
        value = output.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AI analysis is missing required field: {field}")

    key_info = output.get("key_info")
    if not isinstance(key_info, dict):
        raise ValueError("AI analysis is missing required key_info object")

    readability_score = key_info.get("readability_score")
    if (isinstance(readability_score, bool)
            or not isinstance(readability_score, (int, float))
            or not 1 <= readability_score <= 10):
        raise ValueError("AI analysis has an invalid readability_score")

    if doc_category == "contract":
        if "fairness_score" not in key_info:
            raise ValueError("Contract analysis is missing fairness_score")
        fairness_score = key_info["fairness_score"]
        if fairness_score is not None:
            if (isinstance(fairness_score, bool)
                    or not isinstance(fairness_score, (int, float))
                    or not 1 <= fairness_score <= 10):
                raise ValueError("Contract analysis has an invalid fairness_score")
            key_info["fairness_score"] = round(fairness_score, 1)

        justification = key_info.get("score_justification")
        if not isinstance(justification, str) or not justification.strip():
            raise ValueError("Contract analysis is missing score_justification")

        parties = key_info.get("parties")
        if parties is not None and not isinstance(parties, str):
            raise ValueError("Contract analysis has invalid parties information")
        if not parties or not parties.strip() or parties.strip().lower() in {"not applicable", "unknown"}:
            key_info["parties"] = "Not found in document"
        for field in ("financial_terms", "tenure"):
            value = key_info.get(field)
            if not isinstance(value, str) or not value.strip():
                key_info[field] = "Not found in document"
        jurisdiction = output["detected_jurisdiction"].strip()
        if jurisdiction.lower() == "not applicable":
            jurisdiction = "Unknown"
    else:
        jurisdiction = "Not applicable"
        key_info["fairness_score"] = None
        key_info["score_justification"] = "Not applicable — this is not a legal contract"
        for field in ("parties", "financial_terms", "tenure"):
            key_info.pop(field, None)
        output["legal_formalities_guidance"] = "Not applicable — this is not a legal contract."
        output["missing_clauses"] = "Not applicable — this is not a contract."

    key_info["doc_category"] = doc_category
    return {
        "doc_category": doc_category,
        "doc_type": output["doc_type"].strip(),
        "detected_jurisdiction": jurisdiction,
        "key_info": key_info,
        "summary_and_checklist": output["summary_and_checklist"].strip(),
        "risk_analysis": output["risk_analysis"].strip(),
        "questions_to_ask": output["questions_to_ask"].strip(),
        "legal_formalities_guidance": output["legal_formalities_guidance"].strip(),
        "missing_clauses": output["missing_clauses"].strip(),
    }

def _call_model_with_bounded_timeout(client, model_name, prompt, timeout_seconds=14.0):
    """Executes model generation in a worker thread with bounded timeout."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(client.models.generate_content, model=model_name, contents=prompt)
    try:
        res = future.result(timeout=timeout_seconds)
        executor.shutdown(wait=False)
        return res
    except FutureTimeoutError:
        executor.shutdown(wait=False)
        raise TimeoutError(f"Model {model_name} timed out after {timeout_seconds}s")
    except Exception:
        executor.shutdown(wait=False)
        raise

def get_gemini_response(prompt):
    """
    Executes AI prompt against verified primary model ('gemini-3.5-flash') with bounded timeout.
    Selectively retries only transient errors (503, 429, timeout) with single verified fallback
    ('gemini-3.5-flash-lite').
    Logs timing telemetry safely without exposing secrets, prompts, or document content.
    """
    _env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(_env_file):
        load_dotenv(_env_file)
    else:
        load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[AI Error] GEMINI_API_KEY environment variable is missing.")
        return None

    try:
        from google import genai as google_genai
        from google.genai.errors import APIError, ClientError
        client = google_genai.Client(api_key=api_key)
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        print(f"[AI Error] Failed to initialize google.genai Client: {safe_err}")
        return None

    t_ai_total_start = time.time()
    models_sequence = [PRIMARY_GEMINI_MODEL, FALLBACK_GEMINI_MODEL]

    for idx, model_name in enumerate(models_sequence):
        t_model_start = time.time()
        try:
            res = _call_model_with_bounded_timeout(client, model_name, prompt, timeout_seconds=14.0)
            elapsed = time.time() - t_model_start
            total_elapsed = time.time() - t_ai_total_start
            if hasattr(res, 'text') and res.text:
                cleaned_text = res.text.strip().replace('```json', '').replace('```', '').strip()
                print(f"[TIMING AI] Model {model_name} succeeded in {elapsed:.2f}s (Total AI: {total_elapsed:.2f}s)")
                return cleaned_text
            else:
                print(f"[AI Warning] Model {model_name} returned empty text in {elapsed:.2f}s")
        except TimeoutError as te:
            elapsed = time.time() - t_model_start
            print(f"[AI Warning] Model {model_name} timed out after {elapsed:.2f}s ({te})")
            continue
        except Exception as e:
            elapsed = time.time() - t_model_start
            safe_err = sanitize_error_message(str(e))
            status_code = getattr(e, 'code', None)
            # Permanent errors: invalid key, bad request, forbidden, or 404
            if status_code in (400, 401, 403, 404) or "API_KEY_INVALID" in safe_err or "PERMISSION_DENIED" in safe_err:
                print(f"[AI Error] Permanent API failure with {model_name} (code={status_code}) in {elapsed:.2f}s. Not retrying.")
                return None
            print(f"[AI Warning] Transient API issue with {model_name} (code={status_code}) in {elapsed:.2f}s: {safe_err[:120]}")
            continue

    total_elapsed = time.time() - t_ai_total_start
    print(f"[AI Error] All verified AI models failed. Total AI duration: {total_elapsed:.2f}s")
    return None

ANALYZE_CLAUSE_PROMPT = """
Explain the following legal clause from a contract in {jurisdiction} in simple terms and highlight any potential risks for the user. Provide the entire response in the {language} language.
CLAUSE TEXT: "{clause_text}"
EXPLANATION AND RISKS in {language}:
"""

COMPARE_PROMPT = """
You are an expert legal AI. Compare the two document texts below. Provide a bulleted list of the key differences, additions, and removals in "Document B" compared to "Document A". Focus on changes related to finances, dates, and responsibilities. Provide the entire response in the {language} language.
DOCUMENT A (Old): "{doc_a_text}"
DOCUMENT B (New): "{doc_b_text}"
COMPARISON ANALYSIS in {language}:
"""

EXPLAIN_TERM_PROMPT = """
You are an AI legal assistant. Explain the following legal term in one simple sentence, as you would to a non-lawyer.
Provide the entire response in the {language} language.
LEGAL TERM: "{term}"
SIMPLE EXPLANATION:
"""

# --- FLASK ROUTES ---

@app.route('/analyze', methods=['POST'])
def analyze_document():
    t_start = time.time()
    uid = "guest_user"
    if USE_FIREBASE:
        try:
            id_token = request.headers.get('Authorization', '').split(' ').pop()
            uid = auth.verify_id_token(id_token)['uid']
        except Exception:
            return jsonify({"error": "Unauthorized."}), 401
    else:
        auth_header = request.headers.get('Authorization', '')
        if 'Bearer ' in auth_header:
            token = auth_header.split(' ').pop()
            if token and token != "undefined" and token != "null":
                uid = f"local_user_{token[:8]}"
    
    file = request.files.get('document')
    language = request.form.get('language', 'English')
    filename = request.form.get('filename', 'Sample_Rental_Agreement.pdf')
    tags_string = request.form.get('tags', '')
    tags_array = [tag.strip().lower() for tag in tags_string.split(',') if tag.strip()]

    t_extract_start = time.time()
    document_text = None
    file_size = 0
    if file:
        file_extension = os.path.splitext(file.filename)[1].lower()
        document_text = extract_text_from_file(file.stream, file_extension)
        filename = file.filename
        try:
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
        except Exception:
            file_size = len(document_text.encode('utf-8')) if document_text else 0
    t_extract = time.time() - t_extract_start

    # Reject unreadable file uploads with 400
    if file and (not document_text or len(document_text.strip()) < 20):
        return jsonify({
            "error": "Could not extract readable text from the uploaded document. Please check the file format or ensure it contains readable text."
        }), 400

    # Demo mode when no file is uploaded
    if not file:
        document_text = SAMPLE_RENTAL_AGREEMENT
        filename = "Sample_Rental_Agreement.pdf"

    try:
        prompt = CONSOLIDATED_ANALYSIS_PROMPT.format(document_text=document_text, language=language)
        t_ai_start = time.time()
        ai_response_text = get_gemini_response(prompt)
        t_ai = time.time() - t_ai_start
        
        parsed_json = None
        if ai_response_text:
            try:
                json_start = ai_response_text.find('{')
                json_end = ai_response_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response_text[json_start:json_end]
                    parsed_json = json.loads(json_str)
            except Exception as pe:
                print(f"[AI Error] JSON parse error on AI response: {pe}")

        # If AI analysis failed or returned invalid output, do not store fabricated data
        if parsed_json is None:
            t_total = time.time() - t_start
            print(f"[TIMING] /analyze - FAILED (AI service error) | Extract: {t_extract:.3f}s | AI: {t_ai:.3f}s | Total: {t_total:.3f}s")
            return jsonify({
                "error": "AI document analysis service is temporarily unavailable or returned invalid output. Please retry."
            }), 503

        try:
            normalized = normalize_analysis_output(parsed_json)
        except ValueError as validation_error:
            t_total = time.time() - t_start
            print(f"[AI Error] Invalid analysis structure ({validation_error})")
            print(f"[TIMING] /analyze - FAILED (invalid AI output) | Extract: {t_extract:.3f}s | AI: {t_ai:.3f}s | Total: {t_total:.3f}s")
            return jsonify({
                "error": "AI document analysis returned an incomplete or invalid result. Please retry."
            }), 503

        doc_category = normalized["doc_category"]
        doc_type = normalized["doc_type"]
        jurisdiction = normalized["detected_jurisdiction"]
        key_info_json = normalized["key_info"]
        summary_and_checklist = normalized["summary_and_checklist"]
        risk_analysis = normalized["risk_analysis"]
        questions_to_ask = normalized["questions_to_ask"]
        legal_formalities_guidance = normalized["legal_formalities_guidance"]
        missing_clauses = normalized["missing_clauses"]

        doc_id = str(uuid.uuid4())
        created_dt = datetime.datetime.now(tz=datetime.timezone.utc)

        # 1. Document record (documents collection)
        doc_meta = {
            'doc_id': doc_id,
            'filename': filename,
            'file_type': os.path.splitext(filename)[1].lower(),
            'file_size': file_size or (len(document_text.encode('utf-8')) if document_text else 0),
            'source': 'upload' if file else 'sample',
            'status': 'processed',
            'user_id': uid,
            'created_at': created_dt
        }

        # 2. Analysis record (analyses collection)
        analysis_payload = {
            'doc_id': doc_id,
            'filename': filename,
            'doc_type': doc_type,
            'doc_category': doc_category,
            'language': language,
            'jurisdiction': jurisdiction,
            'key_info': key_info_json,
            'summary_and_checklist': summary_and_checklist,
            'risk_analysis': risk_analysis,
            'questions_to_ask': questions_to_ask,
            'legal_formalities_guidance': legal_formalities_guidance,
            'missing_clauses': missing_clauses,
            'tags': tags_array,
            'user_id': uid,
            'created_at': created_dt,
            'analyzedAt': created_dt.isoformat()
        }

        t_db_start = time.time()
        # Primary persistence: MongoDB Atlas
        if USE_MONGODB:
            try:
                DocumentRepository.insert_document(doc_meta)
                AnalysisRepository.insert_analysis(analysis_payload)
            except Exception as dbe:
                safe_err = sanitize_error_message(str(dbe))
                print(f"MongoDB persistence error in /analyze: {safe_err}")
                return jsonify({"error": "Failed to persist document analysis. Please try again."}), 500

        # Secondary persistence: Firebase Firestore if active
        if USE_FIREBASE:
            doc_ref = db.collection('users').document(uid).collection('documents').document()
            doc_ref.set(analysis_payload)
            if not USE_MONGODB:
                doc_id = doc_ref.id
        elif not USE_MONGODB:
            # Fallback memory store when neither persistent database is configured
            if uid not in in_memory_docs:
                in_memory_docs[uid] = {}
            in_memory_docs[uid][doc_id] = analysis_payload
        t_db = time.time() - t_db_start

        t_total = time.time() - t_start
        print(f"[TIMING] /analyze - SUCCESS | Extract: {t_extract:.3f}s | AI: {t_ai:.3f}s | DB: {t_db:.3f}s | Total: {t_total:.3f}s")

        return jsonify({
            "doc_category": doc_category,
            "doc_type": doc_type,
            "detected_jurisdiction": jurisdiction,
            "key_info": key_info_json,
            "ai_model": PRIMARY_GEMINI_MODEL,
            "summary_and_checklist": summary_and_checklist,
            "risk_analysis": risk_analysis,
            "questions_to_ask": questions_to_ask,
            "legal_formalities_guidance": legal_formalities_guidance,
            "missing_clauses": missing_clauses,
            "doc_id": doc_id,
        }), 200
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        print(f"An error occurred in /analyze: {safe_err}")
        return jsonify({"error": f"An error occurred: {safe_err}"}), 500

@app.route('/create_share_link', methods=['POST'])
def create_share_link():
    uid = "guest_user"
    if USE_FIREBASE:
        try:
            id_token = request.headers.get('Authorization', '').split(' ').pop()
            uid = auth.verify_id_token(id_token)['uid']
        except Exception:
            return jsonify({"error": "Unauthorized request."}), 401
    try:
        req_json = request.get_json() or {}
        doc_id = req_json.get('doc_id')
        if not doc_id:
            return jsonify({"error": "Document ID is required."}), 400
        
        analysis_data = None
        if USE_MONGODB:
            try:
                analysis_data = AnalysisRepository.find_by_doc_id(doc_id)
            except Exception as dbe:
                print(f"MongoDB lookup error in create_share_link: {sanitize_error_message(str(dbe))}")

        if not analysis_data and USE_FIREBASE:
            original_doc = db.collection('users').document(uid).collection('documents').document(doc_id).get()
            if original_doc.exists:
                analysis_data = original_doc.to_dict()

        if not analysis_data:
            user_docs = in_memory_docs.get(uid, {})
            analysis_data = user_docs.get(doc_id)
            if not analysis_data:
                # search across all local docs
                for u, dmap in in_memory_docs.items():
                    if doc_id in dmap:
                        analysis_data = dmap[doc_id]
                        break
        
        if not analysis_data:
            return jsonify({"error": "Analysis not found."}), 404

        share_id = str(uuid.uuid4())
        created_dt = datetime.datetime.now(tz=datetime.timezone.utc)
        share_payload = {
            'share_id': share_id,
            'doc_id': doc_id,
            'doc_category': analysis_data.get('doc_category', 'other'),
            'key_info': analysis_data.get('key_info'),
            'questions_to_ask': analysis_data.get('questions_to_ask'),
            'legal_formalities_guidance': analysis_data.get('legal_formalities_guidance'),
            'missing_clauses': analysis_data.get('missing_clauses'),
            'summary_and_checklist': analysis_data.get('summary_and_checklist'),
            'risk_analysis': analysis_data.get('risk_analysis'),
            'filename': analysis_data.get('filename'),
            'doc_type': analysis_data.get('doc_type'),
            'is_revoked': False,
            'createdAt': created_dt.isoformat(),
            'created_at': created_dt
        }

        if USE_MONGODB:
            try:
                SharedAnalysisRepository.insert_share(share_payload)
            except Exception as dbe:
                safe_err = sanitize_error_message(str(dbe))
                print(f"MongoDB share save error: {safe_err}")
                return jsonify({"error": "Could not create share link."}), 500

        if USE_FIREBASE:
            share_ref = db.collection('shared_analyses').document(share_id)
            share_ref.set(share_payload)
        elif not USE_MONGODB:
            in_memory_shared[share_id] = share_payload

        return jsonify({"share_id": share_id}), 200
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        print(f"Error creating share link: {safe_err}")
        return jsonify({"error": "Could not create share link."}), 500

@app.route('/get_shared_analysis/<share_id>', methods=['GET'])
def get_shared_analysis(share_id):
    try:
        if USE_MONGODB:
            share_record = SharedAnalysisRepository.find_by_share_id(share_id)
            if share_record:
                return jsonify(share_record), 200

        if USE_FIREBASE:
            share_doc = db.collection('shared_analyses').document(share_id).get()
            if share_doc.exists:
                return jsonify(share_doc.to_dict()), 200

        if share_id in in_memory_shared:
            return jsonify(in_memory_shared[share_id]), 200

        return jsonify({"error": "Shared analysis not found."}), 404
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        return jsonify({"error": safe_err}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Returns recent document analyses for the Vault view."""
    try:
        limit = min(int(request.args.get('limit', 20)), 50)
        skip = max(int(request.args.get('skip', 0)), 0)
        if USE_MONGODB:
            analyses = AnalysisRepository.list_recent(limit=limit, skip=skip)
            return jsonify({"analyses": analyses, "source": "mongodb"}), 200
        else:
            # Return any local in-memory records
            all_docs = []
            for uid, docs in in_memory_docs.items():
                for doc_id, doc_data in docs.items():
                    item = dict(doc_data)
                    item['doc_id'] = doc_id
                    all_docs.append(item)
            return jsonify({"analyses": all_docs, "source": "in_memory"}), 200
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        return jsonify({"error": safe_err}), 500

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_document_by_id(doc_id):
    """Retrieves an analysis by doc_id."""
    try:
        if USE_MONGODB:
            analysis = AnalysisRepository.find_by_doc_id(doc_id)
            if analysis:
                return jsonify(analysis), 200
        for uid, docs in in_memory_docs.items():
            if doc_id in docs:
                return jsonify(docs[doc_id]), 200
        return jsonify({"error": "Document not found."}), 404
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        return jsonify({"error": safe_err}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Returns health status of the application without leaking secrets."""
    return jsonify({
        "status": "healthy",
        "mongodb_connected": USE_MONGODB,
        "firebase_connected": USE_FIREBASE,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip())
    }), 200

@app.route('/analyze_clause', methods=['POST'])
def analyze_clause():
    t_start = time.time()
    try:
        data = request.get_json() or {}
        clause_text = data.get('clause_text')
        language = data.get('language', 'English')
        jurisdiction = data.get('jurisdiction', 'a general jurisdiction')
        if not clause_text or not clause_text.strip():
            return jsonify({"error": "Clause text is required."}), 400
        prompt = ANALYZE_CLAUSE_PROMPT.format(clause_text=clause_text, language=language, jurisdiction=jurisdiction)
        explanation = get_gemini_response(prompt)
        t_total = time.time() - t_start
        print(f"[TIMING] /analyze_clause - Total: {t_total:.3f}s")
        if not explanation or not explanation.strip():
            return jsonify({"error": "Clause analysis service is temporarily unavailable. Please retry."}), 503
        return jsonify({"explanation": explanation.strip()}), 200
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        print(f"Error in /analyze_clause: {safe_err}")
        return jsonify({"error": "Could not analyze clause."}), 500

@app.route('/compare', methods=['POST'])
def compare():
    t_start = time.time()
    if 'doc_a' not in request.files or 'doc_b' not in request.files:
        return jsonify({"error": "Please upload both documents."}), 400
    language = request.form.get('language', 'English')
    try:
        doc_a_ext = os.path.splitext(request.files['doc_a'].filename)[1].lower()
        doc_b_ext = os.path.splitext(request.files['doc_b'].filename)[1].lower()
        
        t_extract_start = time.time()
        doc_a_text = extract_text_from_file(request.files['doc_a'].stream, doc_a_ext)
        doc_b_text = extract_text_from_file(request.files['doc_b'].stream, doc_b_ext)
        t_extract = time.time() - t_extract_start

        if not doc_a_text or not doc_b_text:
            return jsonify({"error": "Could not extract readable text from one or both documents."}), 400

        prompt = COMPARE_PROMPT.format(doc_a_text=doc_a_text, doc_b_text=doc_b_text, language=language)
        t_ai_start = time.time()
        comparison = get_gemini_response(prompt)
        t_ai = time.time() - t_ai_start
        t_total = time.time() - t_start
        print(f"[TIMING] /compare - Extract: {t_extract:.3f}s | AI: {t_ai:.3f}s | Total: {t_total:.3f}s")

        if not comparison or not comparison.strip():
            return jsonify({"error": "Document comparison service is temporarily unavailable. Please retry."}), 503
        return jsonify({"comparison": comparison.strip()}), 200
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        print(f"Error in /compare: {safe_err}")
        return jsonify({"error": "Could not compare documents."}), 500

@app.route('/explain_term', methods=['POST'])
def explain_term():
    t_start = time.time()
    try:
        data = request.get_json() or {}
        term = data.get('term')
        language = data.get('language', 'English')
        if not term or not term.strip():
            return jsonify({"error": "A legal term is required."}), 400
        prompt = EXPLAIN_TERM_PROMPT.format(term=term.strip(), language=language)
        explanation = get_gemini_response(prompt)
        t_total = time.time() - t_start
        print(f"[TIMING] /explain_term - Total: {t_total:.3f}s")
        if not explanation or not explanation.strip():
            return jsonify({"error": "Legal term explanation is temporarily unavailable. Please retry."}), 503
        return jsonify({"explanation": explanation.strip()}), 200
    except Exception as e:
        safe_err = sanitize_error_message(str(e))
        print(f"Error explaining term: {safe_err}")
        return jsonify({"error": "Could not get an explanation."}), 500

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/share.html')
def serve_share_page():
    return send_from_directory(app.static_folder, 'share.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)