"""Forward-only, versioned, additive schema migrations."""
from sqlalchemy import select, text
from app.models import SchemaMigration, VectorSyncJob
from app.migrate_auth import apply_account_schema

MIGRATIONS = [
    ('001_accounts', apply_account_schema),
    ('002_vector_sync_outbox', lambda connection: VectorSyncJob.__table__.create(bind=connection, checkfirst=True)),
]

def migrate(engine=None):
    if engine is None:
        from app.database import engine
    with engine.begin() as connection:
        if connection.dialect.name == 'postgresql':
            connection.execute(text('SELECT pg_advisory_xact_lock(69001)'))
        SchemaMigration.__table__.create(bind=connection, checkfirst=True)
        applied = set(connection.execute(select(SchemaMigration.version)).scalars())
        for version, apply in MIGRATIONS:
            if version not in applied:
                apply(connection)
                connection.execute(SchemaMigration.__table__.insert().values(version=version))

if __name__ == '__main__':
    migrate()
    print('Schema migrations applied successfully.')
