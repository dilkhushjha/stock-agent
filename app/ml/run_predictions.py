from app.data.database import SessionLocal

from app.ml.prediction_engine import (
    MLPredictionEngine,
)


def main():

    db = SessionLocal()

    try:

        engine = (
            MLPredictionEngine(
                db
            )
        )

        engine.load_model_artifact()

        engine.predict_all()

    finally:

        db.close()


if __name__ == "__main__":
    main()
