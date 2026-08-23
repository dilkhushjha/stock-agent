from app.data.database import Base, engine

# Import models so SQLAlchemy knows about them.
from app.models import Stock, MarketData


def initialize_database():
    Base.metadata.create_all(bind=engine)