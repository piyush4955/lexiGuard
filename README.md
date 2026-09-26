# 🛡️ LexiGuard

> **Understand your legal documents before you sign them.**

LexiGuard is a multilingual, AI-powered legal document analyzer designed to make complex legal documents easier to understand.

It analyzes documents such as **rental agreements, loan contracts, and terms of service** and transforms complicated legal language into clear, actionable information.

Instead of forcing users to read through pages of difficult legal terminology, LexiGuard helps them understand:

* 📄 What the document actually says
* ⚠️ Which clauses may be risky or unfavorable
* 📋 What actions they should consider
* 💬 Answers to specific questions about the document
* 🌐 The analysis in multiple Indian languages

> ⚠️ **Disclaimer:** LexiGuard is an information and analysis tool and does not replace professional legal advice.

---

## ✨ What LexiGuard Does

The core workflow is:

```text
📄 Upload Legal Document
        ↓
📑 Select Document Type
        ↓
🧠 AI-Powered Analysis
        ↓
┌───────────────┬───────────────┬───────────────┐
↓               ↓               ↓
📋 Summary      ⚠️ Risk Radar   ✅ Actionable
                                  Checklist
        ↓
🌐 Choose Language
        ↓
💬 Ask Questions
```

LexiGuard is built around a simple idea:

> **Legal documents should be understandable, not intimidating.**

---

# 🚀 Features

## 1. 📄 Multi-Document Support

LexiGuard can analyze multiple types of commonly encountered legal documents.

Currently supported document categories include:

* 🏠 Rental Agreements
* 💰 Loan Contracts
* 📜 Terms of Service

The user selects the document type so the analysis can be tailored to the type of document being reviewed.

---

## 2. 📤 Legal Document Analysis

Upload a legal document and let LexiGuard analyze its contents using AI.

The system processes the document and extracts useful information that can help the user understand the agreement.

The goal is to transform:

```text
Complex Legal Document
        ↓
    AI Analysis
        ↓
Simple, Understandable Information
```

---

## 3. 📋 AI-Generated Summary

LexiGuard generates a simplified summary of the important parts of the document.

Instead of requiring users to understand every legal phrase, the summary focuses on the key information they should be aware of.

The summary is designed to answer questions such as:

* What is this document about?
* What are the important terms?
* What responsibilities does the user have?
* What obligations exist?
* What important conditions should be noticed?

---

## 4. ⚠️ Risk Radar

The **Risk Radar** identifies clauses or terms that may be potentially risky, unfavorable, or important for the user to review carefully.

Examples of areas that may require attention include:

* Unfavorable obligations
* Potentially restrictive clauses
* Important financial conditions
* Notice or termination conditions
* Other terms that may deserve additional review

The purpose is to help users **notice potentially important clauses instead of overlooking them**.

---

## 5. ✅ Actionable Checklist

Understanding a document is only the first step.

LexiGuard also generates an actionable checklist containing practical next steps based on the document analysis.

This helps transform:

```text
"Here is what your document says."
```

into:

```text
"Here is what you should consider checking or doing next."
```

---

## 6. 🌐 Multilingual Analysis

LexiGuard is designed with multilingual users in mind.

The application supports analysis in:

* 🇬🇧 English
* 🇮🇳 Hinglish
* 🇮🇳 Hindi
* 🇮🇳 Telugu
* 🇮🇳 Tamil
* 🇮🇳 Gujarati

This makes legal information more accessible to users who may be more comfortable reading legal explanations in their preferred language.

---

## 7. 💬 Interactive Q&A

Users can ask specific questions about the document instead of relying only on the generated summary.

For example:

```text
"What happens if I terminate this agreement early?"

"Who is responsible for repairs?"

"Is there a notice period?"

"What happens if I miss a payment?"
```

LexiGuard uses the document context to provide an answer to the user's question.

---

# 🧠 AI-Powered Legal Understanding

LexiGuard uses the **Google Gemini API** to analyze and interpret document content.

The general analysis pipeline is:

```text
                 LEGAL DOCUMENT
                       │
                       ↓
                📄 PDF Parsing
                       │
                       ↓
               Extracted Text
                       │
                       ↓
                 🤖 Gemini AI
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
       Summary      Risk Radar   Checklist
          │            │            │
          └────────────┼────────────┘
                       ↓
                🌐 Translation
                       │
                       ↓
              💬 User Interaction
```

---

# 🏗️ Architecture

LexiGuard follows a simple web application architecture.

```text
                    LEXIGUARD
                        │
             ┌──────────┴──────────┐
             ↓                     ↓
        🖥️ FRONTEND            ⚙️ BACKEND
             │                     │
       HTML / CSS / JS          Python
                                   │
                                 Flask
                                   │
                         ┌─────────┴─────────┐
                         ↓                   ↓
                    📑 PyPDF2          🤖 Gemini API
                         │                   │
                         └─────────┬─────────┘
                                   ↓
                            Analysis Results
                                   │
                                   ↓
                              🖥️ Frontend
```

---

# 🖥️ Project Structure

```text
lexiGuard/
│
├── 📁 .github/
│   └── 📁 workflows/
│
├── 📁 backend/
│   ├── 📄 app.py
│   └── ...
│
├── 📁 frontend/
│   ├── 📄 index.html
│   ├── 📄 style.css
│   ├── 📄 script.js
│   └── ...
│
├── 📄 .gitignore
├── 📄 README.md
└── ...
```

---

# 🛠️ Tech Stack

| Technology              | Purpose                      |
| ----------------------- | ---------------------------- |
| **Python**              | Backend application logic    |
| **Flask**               | Web backend / API layer      |
| **Google Gemini API**   | AI-powered document analysis |
| **google-generativeai** | Gemini API integration       |
| **PyPDF2**              | PDF text extraction          |
| **HTML5**               | Frontend structure           |
| **CSS3**                | Frontend styling             |
| **JavaScript**          | Frontend interaction         |

---

# 📦 Installation

## Prerequisites

Make sure you have installed:

* Python 3.x
* Git
* A Google Gemini API key

---

## 1. Clone the Repository

```bash
git clone https://github.com/piyush4955/lexiGuard.git
cd lexiGuard
```

---

# ⚙️ Backend Setup

## 2. Navigate to the Backend

```bash
cd backend
```

---

## 3. Create a Virtual Environment

### Windows

```powershell
python -m venv venv
```

Activate it:

```powershell
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 4. Install Dependencies

If the project contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

---

# 🔑 Configure Gemini API

Create a `.env` file inside the `backend` directory:

```text
backend/
├── .env
├── app.py
└── ...
```

Add your Gemini API key:

```env
GEMINI_API_KEY="YOUR_API_KEY_HERE"
```

### ⚠️ Security

Never commit your API key to GitHub.

Make sure `.env` is included in `.gitignore`.

---

# ▶️ Run the Application

From the `backend` directory:

```bash
python app.py
```

The Flask application should start locally.

Open your browser and visit:

```text
http://127.0.0.1:5000
```

---

# 🔄 Application Workflow

A typical user interaction looks like this:

### Step 1 — Upload

The user uploads a supported legal document.

```text
📄 Rental Agreement
        or
💰 Loan Contract
        or
📜 Terms of Service
```

### Step 2 — Select Document Type

The user selects the type of document being analyzed.

### Step 3 — Choose Language

The user selects the preferred language for the analysis.

### Step 4 — Analyze

LexiGuard processes the document and sends the relevant information to the AI analysis layer.

### Step 5 — Review Results

The user receives:

```text
📋 Summary
⚠️ Risk Radar
✅ Actionable Checklist
```

### Step 6 — Ask Questions

The user can ask additional questions about the document.

---

# 📊 Analysis Output

LexiGuard focuses on three primary outputs.

## 📋 Summary

A simplified explanation of the document's important terms and conditions.

## ⚠️ Risk Radar

Potentially risky or unfavorable clauses that deserve attention.

## ✅ Actionable Checklist

Practical actions or points the user should consider reviewing.

Together:

```text
                 DOCUMENT
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
       SUMMARY    RISK RADAR  CHECKLIST
          │          │          │
          └──────────┼──────────┘
                     ↓
             BETTER UNDERSTANDING
```

---

# 🌐 Supported Languages

| Language | Supported |
| -------- | :-------: |
| English  |     ✅     |
| Hinglish |     ✅     |
| Hindi    |     ✅     |
| Telugu   |     ✅     |
| Tamil    |     ✅     |
| Gujarati |     ✅     |

---

# 🔐 Privacy & Security

Legal documents can contain highly sensitive information.

Users should take care when uploading documents containing:

* Personal information
* Addresses
* Financial information
* Identification details
* Signatures
* Contract information

### API Key Security

The Gemini API key should always be stored in an environment variable or `.env` file and **never committed to the repository**.

```env
GEMINI_API_KEY="YOUR_API_KEY_HERE"
```

---

# ⚠️ Important Disclaimer

LexiGuard is an **AI-powered legal document analysis and information tool**.

It is intended to help users understand complex legal documents and identify potentially important clauses.

It should **not be considered a substitute for a qualified lawyer or professional legal advice**.

Users should consult a qualified legal professional when making important legal decisions.

---

# 🧪 Testing Checklist

Before considering a release, test the following:

* [ ] Upload a rental agreement
* [ ] Upload a loan contract
* [ ] Upload terms of service
* [ ] Verify PDF text extraction
* [ ] Verify document type selection
* [ ] Generate an AI summary
* [ ] Verify Risk Radar results
* [ ] Generate an actionable checklist
* [ ] Test English analysis
* [ ] Test Hinglish analysis
* [ ] Test Hindi analysis
* [ ] Test Telugu analysis
* [ ] Test Tamil analysis
* [ ] Test Gujarati analysis
* [ ] Ask a question about the document
* [ ] Test invalid/unsupported documents
* [ ] Test missing API key handling
* [ ] Verify API keys are not exposed in the frontend or repository

---

# 🔮 Future Improvements

Potential improvements to LexiGuard include:

* 🔍 Clause-level deep dive
* 📑 Document comparison
* 📝 Clause-by-clause explanations
* 📊 Risk scoring
* 📌 Important clause bookmarking
* 🔄 Version comparison between agreements
* 📤 Export analysis as PDF
* 🧠 Improved contextual Q&A
* 🌐 Additional Indian languages
* 🔐 Enhanced privacy and secure document handling
* 👤 User accounts and saved analyses
* 📚 Legal reference integration
* 🤖 More specialized legal analysis models

---

# 🎯 Project Vision

Legal documents are often written for lawyers, while the people signing them may not have a legal background.

LexiGuard aims to bridge that gap.

```text
              COMPLEX LEGAL LANGUAGE
                       ↓
                  🤖 AI ANALYSIS
                       ↓
             SIMPLE EXPLANATION
                       ↓
               ⚠️ RISK AWARENESS
                       ↓
                ✅ ACTIONABLE
                       ↓
              BETTER UNDERSTANDING
```

The goal is not to replace lawyers.

The goal is to help people **understand what they are reading before making important decisions**.

---

# 👨‍💻 Project

## LexiGuard — Multilingual Legal Document Analyzer

An AI-powered tool designed to make legal documents easier to understand through:

* 📋 Simplified summaries
* ⚠️ Risk detection
* ✅ Actionable checklists
* 🌐 Multilingual analysis
* 💬 Interactive document Q&A

---

## 🔗 Repository

**GitHub:**
https://github.com/piyush4955/lexiGuard

---

> **Don't just sign the document. Understand it first.**
