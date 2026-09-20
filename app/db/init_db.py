"""Database initialization — creates all tables.

Run with: python -m app.db.init_db
"""

import logging

from app.core.database import Base, engine

# Import all models so SQLAlchemy registers them on Base.metadata
from app.models.tenant import Tenant, User  # noqa: F401
from app.models.widget import Widget  # noqa: F401
from app.models.submission import Submission  # noqa: F401

logger = logging.getLogger(__name__)


def init_db():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Done. Tables created.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
