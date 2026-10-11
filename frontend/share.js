import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getFirestore, doc, getDoc } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { apiUrl } from "./config.js";

const firebaseConfig = {
    apiKey: "AIzaSyA33tEkjkJjoZr0l-DNxwevv9phRA9GkjY",
    authDomain: "lexiguide-hackathon-2025.firebaseapp.com",
    projectId: "lexiguide-hackathon-2025",
    storageBucket: "lexiguide-hackathon-2025.firebasestorage.app",
    messagingSenderId: "814528861476",
    appId: "1:814528861476:web:7d3ce97018abd1a8dc0fb1"
};

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const shareId = urlParams.get('id');

    const loadingEl = document.getElementById('loading');
    const contentEl = document.getElementById('content');

    if (!shareId) {
        loadingEl.textContent = "Error: Invalid or missing share link parameter.";
        return;
    }

    try {
        // Try Flask local endpoint first
        let data = null;
        try {
            const resp = await fetch(apiUrl(`/get_shared_analysis/${shareId}`));
            if (resp.ok) {
                data = await resp.json();
            }
        } catch (e) {
            console.log("Local fetch failed, trying Firestore direct...");
        }

        if (!data) {
            const app = initializeApp(firebaseConfig);
            const db = getFirestore(app);
            const docRef = doc(db, 'shared_analyses', shareId);
            const docSnap = await getDoc(docRef);
            if (docSnap.exists()) {
                data = docSnap.data();
            }
        }

        if (data) {
            document.getElementById('filename').textContent = data.filename || "Shared Legal Document";
            document.getElementById('doc-type').textContent = data.doc_type || "Legal Analysis";

            function renderMarkdownSafely(text) {
                if (!text) return "";
                if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
                    let html = marked.parse(text);
                    return DOMPurify.sanitize(html);
                }
                return text;
            }

            document.getElementById('summary-text').innerHTML = renderMarkdownSafely(data.summary_and_checklist) || "Summary not available.";
            document.getElementById('risk-text').innerHTML = renderMarkdownSafely(data.risk_analysis) || "Risk audit not available.";
            
            if (document.getElementById('questions-text')) document.getElementById('questions-text').innerHTML = renderMarkdownSafely(data.questions_to_ask) || "";
            if (document.getElementById('missing-clauses-text')) document.getElementById('missing-clauses-text').innerHTML = renderMarkdownSafely(data.missing_clauses) || "";
            if (document.getElementById('stamp-duty-text')) document.getElementById('stamp-duty-text').innerHTML = renderMarkdownSafely(data.legal_formalities_guidance) || "";

            const docCategory = data.doc_category || "contract";
            const summaryHeading = document.getElementById("summary-heading");
            const riskHeading = document.getElementById("risk-heading");
            const questionsHeading = document.getElementById("questions-heading");
            const missingHeading = document.getElementById("missing-clauses-heading");
            const stampHeading = document.getElementById("stamp-duty-heading");

            if (docCategory === "contract") {
                if (summaryHeading) summaryHeading.textContent = "Summary & Action Checklist";
                if (riskHeading) riskHeading.textContent = "Risk Radar & Flagged Gotchas";
                if (questionsHeading) questionsHeading.textContent = "Negotiation Prompts";
                if (missingHeading) missingHeading.textContent = "Omitted Protections";
                if (stampHeading) stampHeading.textContent = "Stamp Duty & Formalities";
            } else if (docCategory === "academic_informational") {
                if (summaryHeading) summaryHeading.textContent = "Key Concepts & Study Checklist";
                if (riskHeading) riskHeading.textContent = "Key Concepts & Caveats";
                if (questionsHeading) questionsHeading.textContent = "Review Questions";
                if (missingHeading) missingHeading.textContent = "Contract Clauses (Not Applicable)";
                if (stampHeading) stampHeading.textContent = "Document Guidance";
            } else {
                if (summaryHeading) summaryHeading.textContent = "Document Summary & Next Steps";
                if (riskHeading) riskHeading.textContent = "Caveats & Concerns";
                if (questionsHeading) questionsHeading.textContent = "Follow-up Questions";
                if (missingHeading) missingHeading.textContent = "Contract Clauses (Not Applicable)";
                if (stampHeading) stampHeading.textContent = "Document Guidance";
            }

            loadingEl.classList.add('hidden');
            contentEl.classList.remove('hidden');

            if (typeof lucide !== "undefined") lucide.createIcons();
        } else {
            loadingEl.textContent = "Error: Shared analysis not found or link has expired.";
        }
    } catch (error) {
        loadingEl.textContent = "Error fetching analysis: " + error.message;
    }
});
