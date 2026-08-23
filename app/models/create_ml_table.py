from app.data.database import engine
from app.models.ml_prediction import MLPrediction


def create_table():
    MLPrediction.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print(
        "ML predictions table ready."
    )


if __name__ == "__main__":
    create_table()
