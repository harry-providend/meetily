"""SQLAlchemy entities. Every module here must be imported by app.domain.registry so a single
Base.metadata sees all tables (Alembic autogenerate and test create_all both depend on it)."""
