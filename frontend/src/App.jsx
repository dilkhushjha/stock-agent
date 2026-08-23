
import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { getPredictions } from "./services/api";
import MarketRegime from "./components/MarketRegime";

function App() {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [darkMode, setDarkMode] = useState(true);

  useEffect(() => {
    loadPredictions();
  }, []);

  async function loadPredictions() {
    try {
      setLoading(true);
      setError("");

      const data = await getPredictions();

      setPredictions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setError("Unable to connect to the backend API.");
    } finally {
      setLoading(false);
    }
  }

  const stats = useMemo(() => {
    const total = predictions.length;

    const buy = predictions.filter(
      (p) => String(p.signal).toUpperCase() === "BUY"
    ).length;

    const hold = predictions.filter(
      (p) => String(p.signal).toUpperCase() === "HOLD"
    ).length;

    const sell = predictions.filter(
      (p) => String(p.signal).toUpperCase() === "SELL"
    ).length;

    const confidenceValues = predictions
      .map((p) => Number(p.confidence))
      .filter((value) => Number.isFinite(value));

    const averageConfidence =
      confidenceValues.length > 0
        ? confidenceValues.reduce((sum, value) => sum + value, 0) /
        confidenceValues.length
        : 0;

    return {
      total,
      buy,
      hold,
      sell,
      averageConfidence,
    };
  }, [predictions]);

  const topOpportunities = useMemo(() => {
    return [...predictions]
      .sort(
        (a, b) =>
          Number(b.predicted_return_5d || 0) -
          Number(a.predicted_return_5d || 0)
      )
      .slice(0, 5);
  }, [predictions]);

  function formatPercent(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
      return "—";
    }

    return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function formatConfidence(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
      return "—";
    }

    return `${(number * 100).toFixed(0)}%`;
  }

  function signalClass(signal) {
    const value = String(signal || "").toLowerCase();

    if (value === "buy") return "signal-buy";
    if (value === "sell") return "signal-sell";

    return "signal-hold";
  }

  function getStockName(symbol) {
    return `${symbol}`;
  }

  return (
    <div className={darkMode ? "app dark" : "app light"}>
      <header className="dashboard-header">
        <div>
          <h1>Stock Agent</h1>
          <p>AI-powered market prediction dashboard</p>
        </div>



        <div className="header-actions">
          <button
            className="refresh-button"
            onClick={loadPredictions}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>

          <button
            className="theme-button"
            onClick={() => setDarkMode((value) => !value)}
          >
            {darkMode ? "☀ Light" : "☾ Dark"}
          </button>
        </div>
      </header>

      <main className="dashboard-content">

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <MarketRegime />



        <section className="stats-grid">
          <div className="stat-card">
            <span>Total Predictions</span>
            <strong>{stats.total}</strong>
          </div>

          <div className="stat-card buy-card">
            <span>BUY</span>
            <strong>{stats.buy}</strong>
          </div>

          <div className="stat-card hold-card">
            <span>HOLD</span>
            <strong>{stats.hold}</strong>
          </div>

          <div className="stat-card sell-card">
            <span>SELL</span>
            <strong>{stats.sell}</strong>
          </div>

          <div className="stat-card">
            <span>Avg. Confidence</span>
            <strong>
              {formatConfidence(stats.averageConfidence)}
            </strong>
          </div>
        </section>

        <section className="section">
          <div className="section-header">
            <div>
              <h2>Top Opportunities</h2>
              <p>Highest predicted 5-day returns</p>
            </div>
          </div>

          {loading ? (
            <div className="empty-state">
              Loading predictions...
            </div>
          ) : topOpportunities.length === 0 ? (
            <div className="empty-state">
              No predictions available.
            </div>
          ) : (
            <div className="opportunity-grid">
              {topOpportunities.map((prediction) => (
                <div
                  className="opportunity-card"
                  key={prediction.id}
                >
                  <div className="opportunity-top">
                    <div>
                      <h3>
                        {getStockName(prediction.symbol)}
                      </h3>

                      <span
                        className={`signal ${signalClass(
                          prediction.signal
                        )}`}
                      >
                        {prediction.signal || "HOLD"}
                      </span>
                    </div>

                    <strong
                      className={
                        Number(prediction.predicted_return_5d) >= 0
                          ? "positive"
                          : "negative"
                      }
                    >
                      {formatPercent(
                        prediction.predicted_return_5d
                      )}
                    </strong>
                  </div>

                  <div className="opportunity-details">
                    <div>
                      <span>5D</span>
                      <strong>
                        {formatPercent(
                          prediction.predicted_return_5d
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>10D</span>
                      <strong>
                        {formatPercent(
                          prediction.predicted_return_10d
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>20D</span>
                      <strong>
                        {formatPercent(
                          prediction.predicted_return_20d
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Confidence</span>
                      <strong>
                        {formatConfidence(
                          prediction.confidence
                        )}
                      </strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-header">
            <div>
              <h2>ML Predictions</h2>
              <p>Latest predictions generated by the model</p>
            </div>
          </div>

          <div className="table-container">
            {loading ? (
              <div className="empty-state">
                Loading predictions...
              </div>
            ) : predictions.length === 0 ? (
              <div className="empty-state">
                No predictions available.
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Stock</th>
                    <th>Signal</th>
                    <th>5D Return</th>
                    <th>10D Return</th>
                    <th>20D Return</th>
                    <th>Confidence</th>
                    <th>Price</th>
                    <th>Model</th>
                  </tr>
                </thead>

                <tbody>
                  {predictions.map((prediction) => (
                    <tr key={prediction.id}>
                      <td className="stock-name">
                        {getStockName(prediction.symbol)}
                      </td>

                      <td>
                        <span
                          className={`signal ${signalClass(
                            prediction.signal
                          )}`}
                        >
                          {prediction.signal || "HOLD"}
                        </span>
                      </td>

                      <td
                        className={
                          Number(
                            prediction.predicted_return_5d
                          ) >= 0
                            ? "positive"
                            : "negative"
                        }
                      >
                        {formatPercent(
                          prediction.predicted_return_5d
                        )}
                      </td>

                      <td
                        className={
                          Number(
                            prediction.predicted_return_10d
                          ) >= 0
                            ? "positive"
                            : "negative"
                        }
                      >
                        {formatPercent(
                          prediction.predicted_return_10d
                        )}
                      </td>

                      <td
                        className={
                          Number(
                            prediction.predicted_return_20d
                          ) >= 0
                            ? "positive"
                            : "negative"
                        }
                      >
                        {formatPercent(
                          prediction.predicted_return_20d
                        )}
                      </td>

                      <td>
                        {formatConfidence(
                          prediction.confidence
                        )}
                      </td>

                      <td>
                        {Number.isFinite(
                          Number(
                            prediction.price_at_prediction
                          )
                        )
                          ? Number(
                            prediction.price_at_prediction
                          ).toFixed(2)
                          : "—"}
                      </td>

                      <td>
                        {prediction.model_name || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;

