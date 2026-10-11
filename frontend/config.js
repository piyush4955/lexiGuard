// LexiGuard Frontend API Configuration
//
// In production on Vercel:
// Set your deployed Render backend service URL below, or dynamically set
// window.LEXIGUARD_API_BASE_URL before scripts execute.
// Example: window.LEXIGUARD_API_BASE_URL = "https://lexiguard-backend.onrender.com";

const PRODUCTION_API_URL = "https://lexiguard-production.up.railway.app/";

export function getApiBaseUrl() {
    if (typeof window !== "undefined" && window.LEXIGUARD_API_BASE_URL && window.LEXIGUARD_API_BASE_URL.trim() !== "") {
        return window.LEXIGUARD_API_BASE_URL.trim().replace(/\/+$/, "");
    }
    // Local development fallback
    if (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
        // If frontend is served directly by Flask on port 5000, use relative paths
        if (window.location.port === "5000") {
            return "";
        }
        // If frontend is run via live-server or a local dev server on another port (e.g. 3000, 5500)
        return "http://localhost:5000";
    }
    // Production default URL
    return PRODUCTION_API_URL.replace(/\/+$/, "");
}

export function apiUrl(endpoint) {
    const base = getApiBaseUrl();
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    return base ? `${base}${cleanEndpoint}` : cleanEndpoint;
}

if (typeof window !== "undefined") {
    window.apiUrl = apiUrl;
    window.getApiBaseUrl = getApiBaseUrl;
}
