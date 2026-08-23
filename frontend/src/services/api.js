const API_BASE_URL = "http://127.0.0.1:8000";

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    if (!response.ok) throw new Error(`API request failed: ${response.status}`);
    return response.json();
}

export async function getRecommendations(limit = 5) {
    return apiRequest(`/recommendations/?limit=${limit}`);
}

export async function getIntelligenceOverview(limit = 12) {
    return apiRequest(`/intelligence/overview?limit=${limit}`);
}

export async function runLiveAgent() {
    return apiRequest("/agent/run-now", { method: "POST" });
}
