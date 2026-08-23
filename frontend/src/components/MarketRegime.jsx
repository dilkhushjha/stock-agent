import { useEffect, useState } from "react";
import { getMarketRegime } from "../services/api";

export default function MarketRegime() {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");

    useEffect(() => {
        getMarketRegime()
            .then((result) => {
                setData(result);
            })
            .catch((err) => {
                console.error(err);
                setError("Unable to load market regime.");
            });
    }, []);

    if (error) {
        return (
            <div className="card">
                <h2>Market Regime</h2>
                <p>{error}</p>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="card">
                <h2>Market Regime</h2>
                <p>Loading...</p>
            </div>
        );
    }

    const metrics = data.metrics || {};

    return (
        <div className="card">
            <h2>Market Regime</h2>

            <div className="regime-value">
                {data.regime}
            </div>

            <div>
                Confidence:{" "}
                {(data.confidence * 100).toFixed(0)}%
            </div>

            <p>
                {data.reason}
            </p>

            <div className="regime-metrics">
                <div>
                    <strong>5D</strong>
                    <span>
                        {metrics.return_5d?.toFixed(2) ?? "-"}%
                    </span>
                </div>

                <div>
                    <strong>20D</strong>
                    <span>
                        {metrics.return_20d?.toFixed(2) ?? "-"}%
                    </span>
                </div>

                <div>
                    <strong>SMA20</strong>
                    <span>
                        {metrics.distance_sma20?.toFixed(2) ?? "-"}%
                    </span>
                </div>
            </div>
        </div>
    );
}