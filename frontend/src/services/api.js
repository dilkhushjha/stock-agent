const API_BASE_URL = "http://127.0.0.1:8000";

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
    }
    return response.json();
}

export async function getRecommendations(limit = 5) {
    return apiRequest(`/recommendations/?limit=${Math.min(limit, 5)}`);
}

// Backend currently supports a maximum overview limit of 20.
export async function getIntelligenceOverview(limit = 20) {
    return apiRequest(`/intelligence/overview?limit=${Math.min(limit, 20)}`);
}

export async function runLiveAgent() {
    return apiRequest("/agent/run-now", { method: "POST" });
}
