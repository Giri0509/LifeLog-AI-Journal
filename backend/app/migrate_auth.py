"""Compatibility entry point for the versioned schema migration runner."""
from sqlalchemy import inspect, text
from app.models import User, UserSession, DiaryEntry, ChatConversation, ChatMessage

def apply_account_schema(connection):
    User.__table__.create(bind=connection, checkfirst=True)
    UserSession.__table__.create(bind=connection, checkfirst=True)
    for model in (DiaryEntry, ChatConversation):
        table = model.__table__
        if not inspect(connection).has_table(table.name):
            table.create(bind=connection)
        else:
            columns = {column['name'] for column in inspect(connection).get_columns(table.name)}
            if 'user_id' not in columns:
                connection.execute(text(f'ALTER TABLE {table.name} ADD COLUMN user_id INTEGER REFERENCES users(id)'))
        for index in table.indexes:
            if 'user_id' in index.columns.keys():
                index.create(bind=connection, checkfirst=True)
    ChatMessage.__table__.create(bind=connection, checkfirst=True)

if __name__ == '__main__':
    from app.migrations import migrate
    migrate()
    print('Schema migrations applied.')
