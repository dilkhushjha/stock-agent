from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company_exposure import CompanyExposure
from app.models.stock import Stock

from app.intelligence.company_exposures import (
    COMPANY_EXPOSURES,
)


class ExposureService:

    @staticmethod
    def seed(
        db: Session,
    ) -> dict:

        inserted = 0

        for symbol, exposures in COMPANY_EXPOSURES.items():

            stock = db.scalar(
                select(Stock).where(
                    Stock.symbol == symbol
                )
            )

            if not stock:
                continue

            for item in exposures:

                existing = db.scalar(
                    select(CompanyExposure).where(
                        CompanyExposure.stock_id
                        == stock.id,
                        CompanyExposure.factor
                        == item["factor"],
                    )
                )

                if existing:
                    continue

                db.add(
                    CompanyExposure(
                        stock_id=stock.id,
                        factor=item["factor"],
                        exposure_type=item["type"],
                        exposure=item["exposure"],
                        description=item["description"],
                    )
                )

                inserted += 1

        db.commit()

        return {
            "inserted": inserted,
        }