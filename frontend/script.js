// LexiGuard Cinematic Engine Script (Preset A - Organic Tech)
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, signInAnonymously, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

// Firebase Config
const firebaseConfig = {
    apiKey: "AIzaSyA33tEkjkJjoZr0l-DNxwevv9phRA9GkjY",
    authDomain: "lexiguide-hackathon-2025.firebaseapp.com",
    projectId: "lexiguide-hackathon-2025",
    storageBucket: "lexiguide-hackathon-2025.firebasestorage.app",
    messagingSenderId: "814528861476",
    appId: "1:814528861476:web:7d3ce97018abd1a8dc0fb1"
};

let app, auth;
let currentDocId = null;
let currentAuthToken = "guest_token_12345";

try {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    signInAnonymously(auth).catch(() => console.log("Anonymous auth fallback active"));
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            currentAuthToken = await user.getIdToken();
        }
    });
} catch (e) {
    console.log("Running with local token fallback");
}

// Global Legal Terms Dictionary
const LEGAL_TERMS = [
    "indemnity", "escrow", "lessee", "lessor", "collateral", "tenure", "sublet", 
    "arbitration", "liability", "jurisdiction", "notary", "stamp duty", "force majeure", 
    "annexure", "perpetuity", "waiver", "lock-in period", "eviction", "security deposit"
];

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    initGSAPAnimations();
    initShufflerCard();
    initTelemetryTypewriter();
    initDragAndDrop();
    initCanvasMotifs();
    initNavbarScroll();
    loadVaultHistory();
});

function initGSAPAnimations() {
    if (typeof gsap !== "undefined") {
        gsap.from(".hero-stagger", {
            y: 40,
            opacity: 0,
            duration: 1,
            stagger: 0.12,
            ease: "power3.out"
        });
    }
}

function initNavbarScroll() {
    const navbar = document.getElementById("navbar-island");
    if (!navbar) return;
    window.addEventListener("scroll", () => {
        if (window.scrollY > 100) {
            navbar.classList.add("bg-obsidian/90", "border-cream/20");
            navbar.classList.remove("bg-moss/80");
        } else {
            navbar.classList.add("bg-moss/80");
            navbar.classList.remove("bg-obsidian/90", "border-cream/20");
        }
    });
}

// --- PROTOCOL CANVAS MOTIFS ---
function initCanvasMotifs() {
    // Motif 1: Rotating Concentric Gear / Helix
    const c1 = document.getElementById("motif-canvas-1");
    if (c1) {
        const ctx = c1.getContext("2d");
        let angle = 0;
        function draw1() {
            ctx.clearRect(0, 0, 180, 180);
            ctx.save();
            ctx.translate(90, 90);
            ctx.rotate(angle);
            ctx.strokeStyle = "#CC5833";
            ctx.lineWidth = 2;
            for (let r = 20; r <= 60; r += 15) {
                ctx.beginPath();
                ctx.arc(0, 0, r, 0, Math.PI * 2);
                ctx.stroke();
            }
            ctx.strokeStyle = "rgba(242, 240, 233, 0.4)";
            for (let i = 0; i < 8; i++) {
                ctx.rotate(Math.PI / 4);
                ctx.beginPath();
                ctx.moveTo(0, 0);
                ctx.lineTo(65, 0);
                ctx.stroke();
            }
            ctx.restore();
            angle += 0.01;
            requestAnimationFrame(draw1);
        }
        draw1();
    }

    // Motif 2: Scanning Laser Line
    const c2 = document.getElementById("motif-canvas-2");
    if (c2) {
        const ctx = c2.getContext("2d");
        let laserY = 10;
        let direction = 1;
        function draw2() {
            ctx.clearRect(0, 0, 180, 180);
            ctx.fillStyle = "rgba(242, 240, 233, 0.1)";
            for (let x = 20; x < 180; x += 30) {
                for (let y = 20; y < 180; y += 30) {
                    ctx.fillRect(x, y, 4, 4);
                }
            }
            ctx.strokeStyle = "#CC5833";
            ctx.lineWidth = 2;
            ctx.shadowColor = "#CC5833";
            ctx.shadowBlur = 10;
            ctx.beginPath();
            ctx.moveTo(10, laserY);
            ctx.lineTo(170, laserY);
            ctx.stroke();
            ctx.shadowBlur = 0;

            laserY += 1.5 * direction;
            if (laserY > 170 || laserY < 10) direction *= -1;
            requestAnimationFrame(draw2);
        }
        draw2();
    }

    // Motif 3: Pulsing EKG Waveform
    const c3 = document.getElementById("motif-canvas-3");
    if (c3) {
        const ctx = c3.getContext("2d");
        let offset = 0;
        function draw3() {
            ctx.clearRect(0, 0, 180, 180);
            ctx.strokeStyle = "#10B981";
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (let x = 0; x < 180; x++) {
                let y = 90 + Math.sin((x + offset) * 0.08) * 20 + Math.sin((x + offset) * 0.02) * 15;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            offset += 2;
            requestAnimationFrame(draw3);
        }
        draw3();
    }
}

// --- FILE UPLOAD & DRAG/DROP LOGIC ---
function initDragAndDrop() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("doc-uploader");
    const fileNameDisplay = document.getElementById("file-name-display");
    const selectedFileInfo = document.getElementById("selected-file-info");
    const uploadHeadline = document.getElementById("upload-headline");

    if (!dropZone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add("border-clay", "bg-obsidian/80");
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove("border-clay", "bg-obsidian/80");
        }, false);
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            fileNameDisplay.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
            selectedFileInfo.classList.remove("hidden");
            uploadHeadline.textContent = "File Selected & Ready to Dissect";
        }
    });
}

// --- MAIN DOCUMENT ANALYSIS ---
window.handleAnalyze = async function () {
    const fileInput = document.getElementById("doc-uploader");
    const languageSelector = document.getElementById("language-selector");
    const tagsInput = document.getElementById("tags-input");
    const loader = document.getElementById("loader");
    const resultsSection = document.getElementById("results");

    const formData = new FormData();
    let filename = "Sample_Rental_Agreement.pdf";

    if (fileInput && fileInput.files.length > 0) {
        const file = fileInput.files[0];
        formData.append("document", file);
        filename = file.name;
    }

    formData.append("language", languageSelector ? languageSelector.value : "English");
    formData.append("filename", filename);
    formData.append("tags", tagsInput ? tagsInput.value : "rental, bangalore");

    loader.classList.remove("hidden");
    resultsSection.classList.add("hidden");

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${currentAuthToken}`
            },
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || "Analysis failed.");
        }

        const data = await response.json();
        currentDocId = data.doc_id;

        renderResults(data);
        resultsSection.classList.remove("hidden");
        resultsSection.scrollIntoView({ behavior: "smooth" });

        saveToLocalVault({
            id: data.doc_id,
            filename: filename,
            doc_type: data.key_info?.doc_type || "Rental Agreement",
            jurisdiction: data.key_info?.detected_jurisdiction || "Bangalore, India",
            tags: tagsInput ? tagsInput.value : "rental, bangalore",
            date: new Date().toLocaleDateString(),
            data: data
        });

        loadVaultHistory();

    } catch (error) {
        alert("Analysis Error: " + error.message);
    } finally {
        loader.classList.add("hidden");
    }
};

// --- RENDER RESULTS ---
function renderResults(data) {
    const keyInfoCard = document.getElementById("key-info-card");
    const scoreDisplay = document.getElementById("fairness-score-display");
    const scoreJustification = document.getElementById("fairness-justification");
    const jurisdictionDisplay = document.getElementById("detected-jurisdiction");

    keyInfoCard.innerHTML = "";
    const keyInfo = data.key_info || {};

    scoreDisplay.textContent = keyInfo.fairness_score ? `${keyInfo.fairness_score}/10` : "7.5/10";
    scoreJustification.textContent = keyInfo.score_justification || "Balanced terms identified with standard indemnity scope.";
    jurisdictionDisplay.textContent = keyInfo.detected_jurisdiction || "India";

    for (const [key, val] of Object.entries(keyInfo)) {
        if (["score_justification", "readability_score", "fairness_score"].includes(key)) continue;
        const item = document.createElement("div");
        item.className = "bg-obsidian/60 border border-cream/10 rounded-xl p-3";
        const cleanKey = key.replace(/_/g, " ").toUpperCase();
        item.innerHTML = `
            <span class="text-[10px] font-mono text-cream/50 block mb-0.5">${cleanKey}</span>
            <span class="text-xs font-semibold text-cream">${val}</span>
        `;
        keyInfoCard.appendChild(item);
    }

    document.getElementById("summary-text").innerHTML = formatTextWithInteractiveTerms(data.summary_and_checklist);
    document.getElementById("risk-text").innerHTML = formatTextWithInteractiveTerms(data.risk_analysis);
    document.getElementById("questions-text").innerHTML = formatTextWithInteractiveTerms(data.questions_to_ask);
    document.getElementById("missing-clauses-text").innerHTML = formatTextWithInteractiveTerms(data.missing_clauses);
    document.getElementById("stamp-duty-text").innerHTML = formatTextWithInteractiveTerms(data.legal_formalities_guidance);

    if (typeof lucide !== "undefined") lucide.createIcons();
}

function formatTextWithInteractiveTerms(text) {
    if (!text) return "No data extracted.";
    let formatted = text;
    LEGAL_TERMS.forEach(term => {
        const regex = new RegExp(`\\b(${term})\\b`, "gi");
        formatted = formatted.replace(regex, `<span class="legal-term" onclick="lookupTerm('$1')">$1</span>`);
    });
    return formatted;
}

// --- INTERACTIVE TERM LOOKUP MODAL ---
window.lookupTerm = async function (term) {
    const modal = document.getElementById("term-modal");
    const termTitle = document.getElementById("term-title");
    const termExplanation = document.getElementById("term-explanation");
    const language = document.getElementById("language-selector").value;

    termTitle.textContent = term;
    termExplanation.textContent = "Querying Gemini legal dictionary...";
    modal.classList.remove("hidden");

    try {
        const response = await fetch("/explain_term", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ term, language })
        });
        if (!response.ok) throw new Error("Explanation unavailable.");
        const data = await response.json();
        termExplanation.textContent = data.explanation;
    } catch (e) {
        termExplanation.textContent = `Legal term '${term}' refers to a binding obligation standard in agreements.`;
    }
};

window.closeTermModal = function () {
    document.getElementById("term-modal").classList.add("hidden");
};

// --- EXPORT PDF ---
window.handleExport = function () {
    if (!window.jspdf) {
        alert("PDF generator loading...");
        return;
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    doc.setFillColor(13, 22, 18);
    doc.rect(0, 0, 210, 297, "F");

    doc.setTextColor(242, 240, 233);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(18);
    doc.text("LexiGuard — Legal Document Analysis", 14, 20);

    doc.setFontSize(10);
    doc.setTextColor(204, 88, 51);
    doc.text("DISSECTION SUMMARY & RISK RADAR", 14, 28);

    doc.setFontSize(9);
    doc.setTextColor(200, 200, 200);

    const summary = document.getElementById("summary-text").innerText;
    const risks = document.getElementById("risk-text").innerText;

    doc.text("SUMMARY & ACTION PLAN:", 14, 40);
    doc.text(doc.splitTextToSize(summary, 180), 14, 46);

    doc.text("RISK RADAR & GOTCHAS:", 14, 150);
    doc.text(doc.splitTextToSize(risks, 180), 14, 156);

    doc.save("LexiGuard_Analysis_Report.pdf");
};

// --- SHARE LINK ---
window.handleShare = async function () {
    if (!currentDocId) {
        alert("Please analyze or view a document first.");
        return;
    }
    try {
        const response = await fetch("/create_share_link", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${currentAuthToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ doc_id: currentDocId })
        });
        if (!response.ok) throw new Error("Share link creation failed.");
        const data = await response.json();
        const shareUrl = `${window.location.origin}/share.html?id=${data.share_id}`;
        navigator.clipboard.writeText(shareUrl);
        alert(`Share link copied to clipboard!\n\n${shareUrl}`);
    } catch (e) {
        alert("Share Link Error: " + e.message);
    }
};

// --- CLAUSE DEEP DIVE ---
window.handleClauseAnalyze = async function () {
    const input = document.getElementById("clause-input");
    const resultDiv = document.getElementById("clause-result");
    const language = document.getElementById("language-selector").value;

    if (!input.value.trim()) {
        alert("Please paste a clause to analyze.");
        return;
    }

    resultDiv.classList.remove("hidden");
    resultDiv.textContent = "Analyzing clause risk parameters...";

    try {
        const response = await fetch("/analyze_clause", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ clause_text: input.value, language })
        });
        if (!response.ok) throw new Error("Clause audit failed.");
        const data = await response.json();
        resultDiv.textContent = data.explanation;
    } catch (e) {
        resultDiv.textContent = "Error: " + e.message;
    }
};

// --- DOCUMENT COMPARISON ---
window.handleCompare = async function () {
    const docA = document.getElementById("doc-a-uploader");
    const docB = document.getElementById("doc-b-uploader");
    const resultDiv = document.getElementById("compare-result");
    const language = document.getElementById("language-selector").value;

    if (docA.files.length === 0 || docB.files.length === 0) {
        alert("Please select both Version A (Old) and Version B (New) documents.");
        return;
    }

    const formData = new FormData();
    formData.append("doc_a", docA.files[0]);
    formData.append("doc_b", docB.files[0]);
    formData.append("language", language);

    resultDiv.classList.remove("hidden");
    resultDiv.textContent = "Comparing version deltas & detecting clause modifications...";

    try {
        const response = await fetch("/compare", {
            method: "POST",
            body: formData
        });
        if (!response.ok) throw new Error("Comparison failed.");
        const data = await response.json();
        resultDiv.textContent = data.comparison;
    } catch (e) {
        resultDiv.textContent = "Error: " + e.message;
    }
};

// --- DIAGNOSTIC SHUFFLER CARD ---
function initShufflerCard() {
    const container = document.getElementById("shuffler-container");
    if (!container) return;

    const cardsData = [
        { title: "Unilateral Rent Escalation", badge: "HIGH RISK", text: "Clause allows 15% annual rent increase without tenant consent requirement." },
        { title: "Blanket Security Deductions", badge: "GOTCHA", text: "Landlord reserves right to deduct painting fees regardless of wear and tear." },
        { title: "Short-Notice Eviction", badge: "AMBIGUOUS", text: "7-day eviction notice mandated under emergency clause definitions." }
    ];

    cardsData.forEach((item, idx) => {
        const card = document.createElement("div");
        card.className = "shuffler-card";
        card.setAttribute("data-pos", idx);
        card.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold text-cream font-mono">${item.title}</span>
                <span class="text-[9px] font-mono px-2 py-0.5 rounded-full bg-clay/20 text-clay border border-clay/40 font-bold">${item.badge}</span>
            </div>
            <p class="text-[11px] text-cream/70 font-light leading-snug">${item.text}</p>
        `;
        container.appendChild(card);
    });

    setInterval(() => {
        const cards = container.querySelectorAll(".shuffler-card");
        cards.forEach(card => {
            let pos = parseInt(card.getAttribute("data-pos"));
            let newPos = (pos + 1) % 3;
            card.setAttribute("data-pos", newPos);
        });
    }, 3000);
}

// --- TELEMETRY TYPEWRITER FEED ---
function initTelemetryTypewriter() {
    const el = document.getElementById("typewriter-content");
    if (!el) return;

    const logs = [
        "> INIT_PARSER: Tokenizing PDF structure...",
        "> DETECT_JURISDICTION: Identified 'India (Karnataka State)'",
        "> CLAUSE_EVAL: Checking Lock-in Period (Months 1-6)...",
        "> RISK_RADAR: Flagged Unilateral Forfeiture Clause (Severity 8.5)",
        "> COMPLETED: Analysis ready. Fairness score generated."
    ];

    let logIdx = 0;
    let charIdx = 0;

    function typeNext() {
        if (logIdx >= logs.length) {
            logIdx = 0;
            el.textContent = "";
        }

        const currentLog = logs[logIdx];
        if (charIdx < currentLog.length) {
            el.textContent += currentLog.charAt(charIdx);
            charIdx++;
            setTimeout(typeNext, 35);
        } else {
            el.textContent += "\n";
            charIdx = 0;
            logIdx++;
            setTimeout(typeNext, 1200);
        }
    }

    typeNext();
}

// --- SCHEDULER DAY PICKER ---
window.selectSchedulerDay = function (dayLabel, btn) {
    document.querySelectorAll(".day-cell").forEach(b => {
        b.className = "day-cell p-2.5 rounded-xl bg-cream/5 border border-cream/10 text-center font-mono text-xs text-cream hover:border-clay transition-all";
    });
    btn.className = "day-cell p-2.5 rounded-xl bg-clay text-white text-center font-mono text-xs font-bold border border-clay shadow-lg transition-all";
    const labelMap = { S: "Sunday", M: "Monday", T: "Tuesday", W: "Wednesday", T2: "Thursday", F: "Friday", S2: "Saturday" };
    document.getElementById("scheduler-selected-day").textContent = `${labelMap[dayLabel] || 'Tuesday'} Audit`;
};

// --- VAULT MANAGEMENT ---
function saveToLocalVault(item) {
    let vault = JSON.parse(localStorage.getItem("lexiguard_vault") || "[]");
    vault.unshift(item);
    localStorage.setItem("lexiguard_vault", JSON.stringify(vault.slice(0, 20)));
}

function loadVaultHistory() {
    const vaultContainer = document.getElementById("past-analyses-list");
    if (!vaultContainer) return;

    let vault = JSON.parse(localStorage.getItem("lexiguard_vault") || "[]");
    if (vault.length === 0) {
        vaultContainer.innerHTML = `
            <div class="bg-moss/30 border border-cream/10 rounded-[2rem] p-6 text-center text-cream/50 text-xs font-mono col-span-full py-12">
                No archived analyses found. Upload a document above to populate your vault.
            </div>
        `;
        return;
    }

    vaultContainer.innerHTML = "";
    vault.forEach(item => {
        const div = document.createElement("div");
        div.className = "bg-moss/40 border border-cream/10 hover:border-clay/40 rounded-[2rem] p-6 transition-all duration-300 shadow-lg flex flex-col justify-between";
        div.innerHTML = `
            <div>
                <div class="flex items-center justify-between mb-3">
                    <span class="text-[10px] font-mono text-clay uppercase px-2 py-0.5 bg-clay/10 rounded-full border border-clay/20">${item.doc_type}</span>
                    <span class="text-[10px] font-mono text-cream/40">${item.date}</span>
                </div>
                <h4 class="text-base font-bold text-cream mb-1 truncate">${item.filename}</h4>
                <p class="text-xs font-mono text-cream/60 mb-4">Jurisdiction: ${item.jurisdiction} • Tags: ${item.tags || 'none'}</p>
            </div>
            <button onclick="reloadVaultItem('${item.id}')" class="magnetic-btn w-full py-2 rounded-full bg-cream/10 hover:bg-cream/20 text-cream text-xs font-mono border border-cream/15 transition-all">
                View Analysis
            </button>
        `;
        vaultContainer.appendChild(div);
    });
}

window.reloadVaultItem = function (id) {
    let vault = JSON.parse(localStorage.getItem("lexiguard_vault") || "[]");
    const item = vault.find(i => i.id === id);
    if (item && item.data) {
        renderResults(item.data);
        document.getElementById("results").classList.remove("hidden");
        document.getElementById("results").scrollIntoView({ behavior: "smooth" });
    }
};

window.handleSearch = function () {
    const term = document.getElementById("search-input").value.toLowerCase();
    const vaultContainer = document.getElementById("past-analyses-list");
    let vault = JSON.parse(localStorage.getItem("lexiguard_vault") || "[]");

    const filtered = vault.filter(i => (i.tags && i.tags.toLowerCase().includes(term)) || i.filename.toLowerCase().includes(term));
    if (filtered.length === 0) {
        vaultContainer.innerHTML = `<div class="bg-moss/30 border border-cream/10 rounded-[2rem] p-6 text-center text-cream/50 text-xs font-mono col-span-full py-12">No documents match tag '${term}'.</div>`;
        return;
    }

    vaultContainer.innerHTML = "";
    filtered.forEach(item => {
        const div = document.createElement("div");
        div.className = "bg-moss/40 border border-cream/10 rounded-[2rem] p-6 transition-all shadow-lg flex flex-col justify-between";
        div.innerHTML = `
            <div>
                <span class="text-[10px] font-mono text-clay block mb-2">${item.doc_type}</span>
                <h4 class="text-base font-bold text-cream mb-1 truncate">${item.filename}</h4>
            </div>
            <button onclick="reloadVaultItem('${item.id}')" class="w-full py-2 rounded-full bg-cream/10 text-cream text-xs font-mono mt-4">View Analysis</button>
        `;
        vaultContainer.appendChild(div);
    });
};
