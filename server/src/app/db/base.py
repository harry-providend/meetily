from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base -- every entity in app.domain.* inherits from this so a single
    Base.metadata drives both Alembic autogenerate and the test-suite's create_all()."""
