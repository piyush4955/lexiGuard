import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getFirestore, doc, getDoc } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

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
            const resp = await fetch(`/get_shared_analysis/${shareId}`);
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
            document.getElementById('summary-text').textContent = data.summary_and_checklist || "Summary not available.";
            document.getElementById('risk-text').textContent = data.risk_analysis || "Risk audit not available.";

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
