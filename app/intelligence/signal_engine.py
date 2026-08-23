from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company_exposure import (
    CompanyExposure,
)
from app.models.fundamentals import (
    CompanyFundamentals,
)
from app.models.stock import Stock

from app.intelligence.graph_engine import (
    MarketGraph,
)
from app.intelligence.market_regime import (
    MarketRegimeDetector,
)
from app.intelligence.sector_intelligence import (
    SectorIntelligence,
)
from app.intelligence.sector_config import (
    STOCK_SECTORS,
)


class SignalEngine:

    def __init__(self):

        self.graph = MarketGraph()

    def generate(
        self,
        db: Session,
        factor: str,
        direction: str,
    ) -> list[dict]:

        # -----------------------------------------
        # Market regime
        # -----------------------------------------

        regime_data = (
            MarketRegimeDetector.detect()
        )

        regime = regime_data.get(
            "regime",
            "UNKNOWN",
        )

        regime_confidence = regime_data.get(
            "confidence",
            0.0,
        )

        # -----------------------------------------
        # Find companies exposed to factor
        # -----------------------------------------

        exposures = db.scalars(
            select(CompanyExposure).where(
                CompanyExposure.factor
                == factor.upper()
            )
        ).all()

        signals = []

        for exposure in exposures:

            # -------------------------------------
            # Get stock
            # -------------------------------------

            stock = db.scalar(
                select(Stock).where(
                    Stock.id == exposure.stock_id
                )
            )

            if not stock:
                continue

            # -------------------------------------
            # Fundamentals
            # -------------------------------------

            fundamentals = db.scalar(
                select(CompanyFundamentals).where(
                    CompanyFundamentals.stock_id
                    == stock.id
                )
            )

            fundamental_score = 50.0

            if fundamentals:

                if fundamentals.roe is not None:

                    if fundamentals.roe > 0.15:
                        fundamental_score += 10

                if (
                    fundamentals.earnings_growth
                    is not None
                ):

                    if (
                        fundamentals.earnings_growth
                        > 0.10
                    ):
                        fundamental_score += 10

                if (
                    fundamentals.debt_to_equity
                    is not None
                ):

                    if (
                        fundamentals.debt_to_equity
                        < 1
                    ):
                        fundamental_score += 5

            # -------------------------------------
            # Knowledge graph impact
            # -------------------------------------

            impacts = self.graph.calculate_impact(
                factor,
                direction,
            )

            matching_impacts = [
                item
                for item in impacts
                if item["target"]
                in self._company_categories(
                    stock.symbol
                )
            ]

            impact_score = 0.0
            impact_direction = "NEUTRAL"

            if matching_impacts:

                strongest = max(
                    matching_impacts,
                    key=lambda x: x["impact_score"],
                )

                impact_score = (
                    strongest["impact_score"]
                    * exposure.exposure
                )

                impact_direction = (
                    strongest["resulting_impact"]
                )

            # -------------------------------------
            # Base signal score
            # -------------------------------------

            total_score = (
                fundamental_score * 0.35
                + impact_score * 100 * 0.65
            )

            if impact_direction == "NEGATIVE":

                total_score *= -1

            # -------------------------------------
            # Market regime adjustment
            # -------------------------------------

            regime_adjustment = 1.0

            if regime == "BULL":

                if impact_direction == "POSITIVE":

                    regime_adjustment = 1.10

                elif impact_direction == "NEGATIVE":

                    regime_adjustment = 0.90

            elif regime == "BEAR":

                if impact_direction == "POSITIVE":

                    regime_adjustment = 0.90

                elif impact_direction == "NEGATIVE":

                    regime_adjustment = 1.10

            elif regime == "HIGH_VOLATILITY":

                regime_adjustment = 0.85

            total_score *= regime_adjustment

            # -------------------------------------
            # Sector intelligence
            # -------------------------------------

            sector = STOCK_SECTORS.get(
                stock.symbol
            )

            sector_data = None

            if sector:

                sector_data = (
                    SectorIntelligence
                    .get_sector_data(sector)
                )

            sector_adjustment = 1.0

            if sector_data:

                sector_trend = (
                    sector_data.get("trend")
                )

                sector_breadth = (
                    sector_data.get("breadth")
                )

                # ---------------------------------
                # Sector trend confirmation
                # ---------------------------------

                if (
                    impact_direction == "POSITIVE"
                    and sector_trend == "BULLISH"
                ):

                    sector_adjustment = 1.10

                elif (
                    impact_direction == "POSITIVE"
                    and sector_trend == "BEARISH"
                ):

                    sector_adjustment = 0.90

                elif (
                    impact_direction == "NEGATIVE"
                    and sector_trend == "BEARISH"
                ):

                    sector_adjustment = 1.10

                elif (
                    impact_direction == "NEGATIVE"
                    and sector_trend == "BULLISH"
                ):

                    sector_adjustment = 0.90

                # ---------------------------------
                # Breadth confirmation
                # ---------------------------------

                if sector_breadth is not None:

                    if (
                        impact_direction == "POSITIVE"
                        and sector_breadth >= 70
                    ):

                        sector_adjustment *= 1.05

                    elif (
                        impact_direction == "POSITIVE"
                        and sector_breadth <= 30
                    ):

                        sector_adjustment *= 0.95

                    elif (
                        impact_direction == "NEGATIVE"
                        and sector_breadth <= 30
                    ):

                        sector_adjustment *= 1.05

                    elif (
                        impact_direction == "NEGATIVE"
                        and sector_breadth >= 70
                    ):

                        sector_adjustment *= 0.95

            total_score *= sector_adjustment

            # -------------------------------------
            # Final signal
            # -------------------------------------

            signals.append(
                {
                    "symbol": stock.symbol,

                    "factor": factor.upper(),

                    "direction": direction.upper(),

                    "exposure": exposure.exposure,

                    "impact": impact_direction,

                    "fundamental_score": round(
                        fundamental_score,
                        2,
                    ),

                    "signal_score": round(
                        total_score,
                        2,
                    ),

                    # Market context
                    "market_regime": regime,

                    "regime_confidence": (
                        regime_confidence
                    ),

                    "regime_adjustment": (
                        regime_adjustment
                    ),

                    # Sector context
                    "sector": sector,

                    "sector_trend": (
                        sector_data.get(
                            "trend"
                        )
                        if sector_data
                        else None
                    ),

                    "sector_return_20d": (
                        sector_data.get(
                            "return_20d"
                        )
                        if sector_data
                        else None
                    ),

                    "sector_breadth": (
                        sector_data.get(
                            "breadth"
                        )
                        if sector_data
                        else None
                    ),

                    "sector_volatility": (
                        sector_data.get(
                            "volatility"
                        )
                        if sector_data
                        else None
                    ),

                    "sector_adjustment": (
                        sector_adjustment
                    ),
                }
            )

        # -----------------------------------------
        # Rank signals
        # -----------------------------------------

        signals.sort(
            key=lambda x: abs(
                x["signal_score"]
            ),
            reverse=True,
        )

        return signals

    @staticmethod
    def _company_categories(
        symbol: str,
    ) -> list[str]:

        mapping = {

            "BALRAMCHIN": [
                "SUGAR_PRODUCER",
            ],

            "DABUR": [
                "BEVERAGES",
                "CONSUMER",
            ],

            "INDIGO": [
                "AIRLINES",
            ],

            "ASIANPAINT": [
                "PAINTS",
            ],

            "TATASTEEL": [
                "STEEL",
            ],
        }

        return mapping.get(
            symbol,
            [],
        )