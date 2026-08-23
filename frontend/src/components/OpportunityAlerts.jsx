import { useEffect, useRef, useState } from "react";
import { getOpportunityAlerts, markAlertRead } from "../services/api";

function OpportunityAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");
  const [notificationEnabled, setNotificationEnabled] = useState(
    typeof Notification !== "undefined" && Notification.permission === "granted"
  );
  const knownIds = useRef(new Set());
  const firstLoad = useRef(true);

  async function loadAlerts() {
    try {
      const data = await getOpportunityAlerts(20);
      const nextAlerts = Array.isArray(data) ? data : [];

      if (!firstLoad.current && notificationEnabled && typeof Notification !== "undefined") {
        nextAlerts
          .filter((alert) => alert.status === "NEW" && !knownIds.current.has(alert.id))
          .forEach((alert) => {
            new Notification(`Stock Agent: ${alert.action} ${alert.symbol}`, {
              body: `${alert.title}\nConfidence ${(Number(alert.confidence) * 100).toFixed(0)}% | Score ${Number(alert.opportunity_score).toFixed(0)}/100`,
            });
          });
      }

      nextAlerts.forEach((alert) => knownIds.current.add(alert.id));
      firstLoad.current = false;
      setAlerts(nextAlerts);
      setError("");
    } catch (err) {
      console.error(err);
      setError("Unable to load opportunity alerts.");
    }
  }

  useEffect(() => {
    loadAlerts();
    const timer = setInterval(loadAlerts, 60_000);
    return () => clearInterval(timer);
  }, [notificationEnabled]);

  async function enableNotifications() {
    if (typeof Notification === "undefined") return;
    const permission = await Notification.requestPermission();
    setNotificationEnabled(permission === "granted");
  }

  async function readAlert(id) {
    try {
      await markAlertRead(id);
      setAlerts((current) =>
        current.map((alert) =>
          alert.id === id ? { ...alert, status: "READ" } : alert
        )
      );
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <section className="section">
      <div className="section-header">
        <div>
          <h2>🚨 Opportunity Alerts</h2>
          <p>Events the agent believes may create actionable opportunities</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {typeof Notification !== "undefined" && !notificationEnabled && (
            <button className="refresh-button" onClick={enableNotifications}>
              Enable Notifications
            </button>
          )}
          <button className="refresh-button" onClick={loadAlerts}>Refresh Alerts</button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {alerts.length === 0 ? (
        <div className="empty-state">No high-priority opportunities detected yet.</div>
      ) : (
        <div className="opportunity-grid">
          {alerts.map((alert) => (
            <article
              key={alert.id}
              className="opportunity-card"
              style={{ opacity: alert.status === "READ" ? 0.65 : 1 }}
            >
              <div className="opportunity-top">
                <div>
                  <h3>{alert.symbol}</h3>
                  <span className={`signal ${
                    alert.action === "BUY" ? "signal-buy" :
                    alert.action === "AVOID" ? "signal-sell" : "signal-hold"
                  }`}>
                    {alert.action}
                  </span>
                </div>
                <strong>{Number(alert.opportunity_score).toFixed(0)}/100</strong>
              </div>

              <p style={{ margin: "14px 0 8px" }}>{alert.title}</p>
              <p style={{ margin: 0, lineHeight: 1.6 }}>{alert.reason}</p>

              <div className="opportunity-details" style={{ marginTop: 16 }}>
                <div><span>Confidence</span><strong>{(Number(alert.confidence) * 100).toFixed(0)}%</strong></div>
                <div><span>Risk</span><strong>{alert.risk}</strong></div>
                <div><span>Horizon</span><strong>{alert.expected_horizon || "—"}</strong></div>
              </div>

              <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
                {alert.source_url && (
                  <a href={alert.source_url} target="_blank" rel="noreferrer">View source</a>
                )}
                {alert.status !== "READ" && (
                  <button className="refresh-button" onClick={() => readAlert(alert.id)}>Mark read</button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default OpportunityAlerts;
