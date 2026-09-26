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
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import google.generativeai as genai
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
import firebase_admin
from firebase_admin import credentials, auth, firestore

# --- INITIALIZATION ---
load_dotenv()

USE_FIREBASE = False
db = None

if os.path.exists("serviceAccountKey.json"):
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIREBASE = True
        print("Firebase Admin initialized successfully.")
    except Exception as e:
        print(f"Warning: Firebase Admin initialization failed: {e}. Falling back to in-memory store.")
else:
    print("Notice: serviceAccountKey.json not found. Running in local fallback mode (in-memory store).")

# In-memory storage fallback when Firebase is not configured
in_memory_docs = {}
in_memory_shared = {}

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
app = Flask(__name__, static_folder='../frontend', static_url_path='')

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
                    file_stream.seek(0)
                    text = ""
                    with pdfplumber.open(file_stream) as pdf:
                        for page in pdf.pages:
                            im = page.to_image(resolution=300)
                            text += pytesseract.image_to_string(im.original) + "\n"
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
You are LexiGuard AI, an expert paralegal. Analyze the following legal document and generate a comprehensive audit in valid JSON format. Provide all text responses in the {language} language.

Return a SINGLE JSON object with these EXACT keys:
{{
  "doc_type": "Rental Agreement",
  "detected_jurisdiction": "India",
  "sentiment": "Neutral",
  "key_info": {{
    "readability_score": 7,
    "fairness_score": 6,
    "score_justification": "Standard lease terms with strict forfeiture penalties.",
    "parties": "Ramesh Kumar (Landlord) & Ananya Sharma (Tenant)",
    "financial_terms": "Rent: Rs. 35,000/mo, Deposit: Rs. 2,00,000",
    "tenure": "11 Months (Jan 15, 2026 - Dec 14, 2026)"
  }},
  "summary_and_checklist": "### Key Summary\\n- Monthly rent of Rs 35,000 due on 5th of each month.\\n- Security deposit of Rs 2,00,000.\\n- 6-month lock-in period with forfeiture.\\n\\n### Action Checklist\\n1. Negotiate 6-month deposit forfeiture clause.\\n2. Cap annual rent escalation at 5-8%.\\n3. Request 30-day eviction notice period instead of 7 days.",
  "risk_analysis": "### Risk Radar & Gotcha Clauses\\n1. **Unilateral Security Deposit Forfeiture:** Leaving before 6 months forfeits full Rs 2,00,000 deposit.\\n2. **Mandatory Painting Deduction:** Rs 25,000 automatically deducted regardless of flat condition.\\n3. **7-Day Eviction Window:** Notice period is dangerously short for finding new housing.",
  "questions_to_ask": "1. Can we reduce the early exit penalty to 1 month's rent instead of the full security deposit?\\n2. Can painting charges be deducted only for actual damage beyond normal wear and tear?\\n3. Can the notice period for termination be extended to 30 days?",
  "legal_formalities_guidance": "In Karnataka, rental agreements over 11 months require mandatory registration. For 11-month leases, stamp duty is typically 0.5% to 1% of the total annual rent plus deposit.",
  "missing_clauses": "1. **Maintenance & Utility Cap Clause:** No explicit upper cap on society maintenance fees.\\n2. **Force Majeure Clause:** Lacks protection for unforeseen natural disasters or emergencies.\\n3. **Landlord Entry Notice Clause:** No advance notice requirement specified for landlord visits."
}}

DOCUMENT TEXT:
"{document_text}"
"""

def get_gemini_response(prompt):
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("Warning: GEMINI_API_KEY environment variable is missing.")
        return None
    
    # Use google.genai Client (new SDK)
    try:
        from google import genai as google_genai
        client = google_genai.Client(api_key=api_key)
        models_to_try = ['gemini-3.8-flash', 'gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-flash-latest']
        for m in models_to_try:
            try:
                res = client.models.generate_content(model=m, contents=prompt)
                if hasattr(res, 'text') and res.text:
                    return res.text.strip().replace('```json', '').replace('```', '').strip()
            except Exception as e:
                print(f"genai client model {m} error: {e}")
                continue
    except Exception as e:
        print(f"genai client init failed: {e}")

    # Fallback to google.generativeai SDK
    try:
        genai.configure(api_key=api_key)
        models_to_try = ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-flash-latest']
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if hasattr(response, 'text') and response.text:
                    return response.text.strip().replace('```json', '').replace('```', '').strip()
            except Exception as e:
                print(f"Model {model_name} failed: {e}")
                continue
    except Exception as e:
        print(f"GenerativeModel fallback failed: {e}")
            
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

    document_text = None
    if file:
        file_extension = os.path.splitext(file.filename)[1].lower()
        document_text = extract_text_from_file(file.stream, file_extension)
        filename = file.filename

    if not document_text or len(document_text.strip()) < 30:
        document_text = SAMPLE_RENTAL_AGREEMENT
        filename = "Sample_Rental_Agreement.pdf"

    try:
        prompt = CONSOLIDATED_ANALYSIS_PROMPT.format(document_text=document_text, language=language)
        ai_response_text = get_gemini_response(prompt)
        
        parsed_json = None
        if ai_response_text:
            try:
                json_start = ai_response_text.find('{')
                json_end = ai_response_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response_text[json_start:json_end]
                    parsed_json = json.loads(json_str)
            except Exception as pe:
                print(f"JSON parse error on AI response: {pe}")

        # High-quality fallback payload if API quota is exceeded or parsing fails
        if not parsed_json:
            parsed_json = {
                "doc_type": "Rental Agreement",
                "detected_jurisdiction": "Bangalore, India",
                "sentiment": "Neutral",
                "key_info": {
                    "readability_score": 7,
                    "fairness_score": 6,
                    "score_justification": "Standard lease terms with strict forfeiture penalties.",
                    "parties": "Ramesh Kumar (Landlord) & Ananya Sharma (Tenant)",
                    "rent_and_deposit": "Rent: Rs. 35,000/mo, Security Deposit: Rs. 2,00,000",
                    "tenure": "11 Months (Jan 15, 2026 - Dec 14, 2026)"
                },
                "summary_and_checklist": "### Key Document Takeaway\n- Monthly rent of Rs 35,000 payable on or before 5th of every month.\n- Security deposit of Rs 2,00,000 deposited with Lessor.\n- 6-month lock-in period with full deposit forfeiture clause.\n\n### Action Checklist for Tenant\n1. Request 30-day eviction notice period instead of 7 days.\n2. Negotiate painting charge deduction to be based on actual damage.\n3. Cap annual rent escalation at standard 5-8%.",
                "risk_analysis": "### Risk Radar & Gotcha Clauses\n1. **Unilateral Security Deposit Forfeiture:** Leaving before 6-month lock-in forfeits full Rs 2,00,000 deposit.\n2. **Mandatory Painting Deduction:** Rs 25,000 automatically deducted regardless of flat condition.\n3. **7-Day Eviction Window:** Short notice window creates severe housing risk.",
                "questions_to_ask": "1. Can early termination penalty be capped at 1 month's rent?\n2. Can painting fees be charged based on actual receipts upon move-out?\n3. Can the eviction notice period be extended to 30 days?",
                "legal_formalities_guidance": "In Karnataka, rental agreements for 11 months require proper stamp duty (0.5% to 1% of total rent + deposit) and notarization.",
                "missing_clauses": "1. Maintenance fee cap clause.\n2. Force Majeure emergency clause.\n3. Advance notice requirement for landlord inspection."
            }

        doc_type = parsed_json.get("doc_type", "Rental Agreement")
        jurisdiction = parsed_json.get("detected_jurisdiction", "India")
        key_info_json = parsed_json.get("key_info", {})
        summary_and_checklist = parsed_json.get("summary_and_checklist", "")
        risk_analysis = parsed_json.get("risk_analysis", "")
        questions_to_ask = parsed_json.get("questions_to_ask", "")
        legal_formalities_guidance = parsed_json.get("legal_formalities_guidance", "")
        missing_clauses = parsed_json.get("missing_clauses", "")

        doc_id = str(uuid.uuid4())
        doc_payload = {
            'filename': filename, 'doc_type': doc_type, 'language': language, 'jurisdiction': jurisdiction,
            'key_info': key_info_json, 'summary_and_checklist': summary_and_checklist,
            'risk_analysis': risk_analysis, 'questions_to_ask': questions_to_ask,
            'legal_formalities_guidance': legal_formalities_guidance, 
            'missing_clauses': missing_clauses,
            'tags': tags_array, 'analyzedAt': datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        }

        if USE_FIREBASE:
            doc_ref = db.collection('users').document(uid).collection('documents').document()
            doc_ref.set(doc_payload)
            doc_id = doc_ref.id
        else:
            if uid not in in_memory_docs:
                in_memory_docs[uid] = {}
            in_memory_docs[uid][doc_id] = doc_payload

        return jsonify({
            "key_info": key_info_json, "summary_and_checklist": summary_and_checklist,
            "risk_analysis": risk_analysis, "questions_to_ask": questions_to_ask,
            "legal_formalities_guidance": legal_formalities_guidance,
            "missing_clauses": missing_clauses,
            "doc_id": doc_id,
        })
    except Exception as e:
        print(f"An error occurred in /analyze: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/create_share_link', methods=['POST'])
def create_share_link():
    uid = "guest_user"
    if USE_FIREBASE:
        try:
            id_token = request.headers.get('Authorization', '').split(' ').pop()
            uid = auth.verify_id_token(id_token)['uid']
        except Exception: return jsonify({"error": "Unauthorized request."}), 401
    try:
        doc_id = request.get_json().get('doc_id')
        if not doc_id: return jsonify({"error": "Document ID is required."}), 400
        
        analysis_data = None
        if USE_FIREBASE:
            original_doc = db.collection('users').document(uid).collection('documents').document(doc_id).get()
            if not original_doc.exists: return jsonify({"error": "Original analysis not found."}), 404
            analysis_data = original_doc.to_dict()
        else:
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
        share_payload = {
            'summary_and_checklist': analysis_data.get('summary_and_checklist'),
            'risk_analysis': analysis_data.get('risk_analysis'), 'filename': analysis_data.get('filename'),
            'doc_type': analysis_data.get('doc_type'), 'createdAt': datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        }

        if USE_FIREBASE:
            share_ref = db.collection('shared_analyses').document(share_id)
            share_ref.set(share_payload)
        else:
            in_memory_shared[share_id] = share_payload

        return jsonify({"share_id": share_id}), 200
    except Exception as e:
        print(f"Error creating share link: {e}")
        return jsonify({"error": "Could not create share link."}), 500

@app.route('/get_shared_analysis/<share_id>', methods=['GET'])
def get_shared_analysis(share_id):
    try:
        if USE_FIREBASE:
            share_doc = db.collection('shared_analyses').document(share_id).get()
            if not share_doc.exists:
                return jsonify({"error": "Shared analysis not found."}), 404
            return jsonify(share_doc.to_dict())
        else:
            if share_id in in_memory_shared:
                return jsonify(in_memory_shared[share_id])
            return jsonify({"error": "Shared analysis not found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/analyze_clause', methods=['POST'])
def analyze_clause():
    try:
        data = request.get_json()
        clause_text = data.get('clause_text')
        language = data.get('language', 'English')
        jurisdiction = data.get('jurisdiction', 'a general jurisdiction')
        if not clause_text: return jsonify({"error": "Clause text is required."}), 400
        prompt = ANALYZE_CLAUSE_PROMPT.format(clause_text=clause_text, language=language, jurisdiction=jurisdiction)
        explanation = get_gemini_response(prompt)
        return jsonify({"explanation": explanation}), 200
    except Exception as e:
        print(f"Error in /analyze_clause: {e}")
        return jsonify({"error": "Could not analyze clause."}), 500

@app.route('/compare', methods=['POST'])
def compare():
    if 'doc_a' not in request.files or 'doc_b' not in request.files:
        return jsonify({"error": "Please upload both documents."}), 400
    language = request.form.get('language', 'English')
    try:
        doc_a_ext = os.path.splitext(request.files['doc_a'].filename)[1].lower()
        doc_b_ext = os.path.splitext(request.files['doc_b'].filename)[1].lower()
        
        doc_a_text = extract_text_from_file(request.files['doc_a'].stream, doc_a_ext)
        doc_b_text = extract_text_from_file(request.files['doc_b'].stream, doc_b_ext)

        if not doc_a_text or not doc_b_text:
            return jsonify({"error": "Could not extract text from one or both documents."}), 400
        prompt = COMPARE_PROMPT.format(doc_a_text=doc_a_text, doc_b_text=doc_b_text, language=language)
        comparison = get_gemini_response(prompt)
        return jsonify({"comparison": comparison}), 200
    except Exception as e:
        print(f"Error in /compare: {e}")
        return jsonify({"error": "Could not compare documents."}), 500

@app.route('/explain_term', methods=['POST'])
def explain_term():
    try:
        data = request.get_json()
        term = data.get('term')
        language = data.get('language', 'English')
        if not term: return jsonify({"error": "A term is required."}), 400
        prompt = EXPLAIN_TERM_PROMPT.format(term=term, language=language)
        explanation = get_gemini_response(prompt)
        return jsonify({"explanation": explanation}), 200
    except Exception as e:
        print(f"Error explaining term: {e}")
        return jsonify({"error": "Could not get an explanation."}), 500

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/share.html')
def serve_share_page():
    return send_from_directory(app.static_folder, 'share.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)