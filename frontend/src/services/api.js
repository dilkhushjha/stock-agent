const API_BASE_URL = "http://127.0.0.1:8080";

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    if (!response.ok) throw new Error(`API request failed: ${response.status}`);
    return response.json();
}

export async function getRecommendations(limit = 10) {
    return apiRequest(`/recommendations/?limit=${Math.min(limit, 10)}`);
}

export async function getIntelligenceOverview(limit = 20) {
    return apiRequest(`/intelligence/overview?limit=${Math.min(limit, 20)}`);
}

export async function getLiveAlerts(limit = 10) {
    return apiRequest(`/alerts/live?limit=${Math.min(limit, 10)}`);
}

export async function markAlertRead(id) {
    return apiRequest(`/alerts/${id}/read`, { method: "PATCH" });
}

export async function runLiveAgent() {
    return apiRequest("/agent/run-now", { method: "POST" });
}

export async function getAgentStatus() {
    return apiRequest("/agent/status");
}
