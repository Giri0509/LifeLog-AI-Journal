"""Initialize or upgrade the schema using the versioned migration runner."""
from app.migrations import migrate
if __name__ == '__main__':
    migrate()
    print('Database schema is ready.')
