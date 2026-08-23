from app.intelligence.market_graph import (
    MARKET_RELATIONSHIPS,
)


class MarketGraph:

    def __init__(self):

        self.relationships = (
            MARKET_RELATIONSHIPS
        )

    def find_impacts(
        self,
        source: str,
    ) -> list[dict]:

        source = source.upper()

        return [
            relationship
            for relationship in self.relationships
            if relationship["source"]
            == source
        ]

    def calculate_impact(
        self,
        source: str,
        direction: str,
    ) -> list[dict]:

        relationships = self.find_impacts(
            source
        )

        results = []

        for relationship in relationships:

            impact = relationship["impact"]

            if direction.upper() == "DOWN":

                if impact == "POSITIVE":
                    final_impact = "NEGATIVE"

                elif impact == "NEGATIVE":
                    final_impact = "POSITIVE"

                else:
                    final_impact = "MIXED"

            else:

                final_impact = impact

            results.append(
                {
                    **relationship,
                    "event_direction": direction,
                    "resulting_impact": final_impact,
                    "impact_score": round(
                        relationship["sensitivity"],
                        2,
                    ),
                }
            )

        return results