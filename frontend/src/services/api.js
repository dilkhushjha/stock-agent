const API_BASE_URL = "http://127.0.0.1:8000";

async function apiRequest(endpoint) {
    const response = await fetch(
        `${API_BASE_URL}${endpoint}`
    );

    if (!response.ok) {
        throw new Error(
            `API request failed: ${response.status}`
        );
    }

    return response.json();
}

export async function getPredictions(limit = 50) {
    return apiRequest(
        `/predictions/?limit=${limit}`
    );
}

export async function getMarketRegime() {
    return apiRequest(
        "/regime/"
    );
}