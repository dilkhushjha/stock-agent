const API_BASE_URL = "http://127.0.0.1:8000";

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    if (!response.ok) throw new Error(`API request failed: ${response.status}`);
    return response.json();
}

export async function getPredictions(limit = 50) {
    return apiRequest(`/predictions/?limit=${limit}`);
}

export async function getMarketRegime() {
    return apiRequest("/regime/");
}

export async function getOpportunityAlerts(limit = 20) {
    return apiRequest(`/alerts/latest?limit=${limit}`);
}

export async function markAlertRead(id) {
    return apiRequest(`/alerts/${id}/read`, { method: "PATCH" });
}

export async function runLiveAgent() {
    return apiRequest("/agent/run-now", { method: "POST" });
}
