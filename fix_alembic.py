from app.database.session import engine
from sqlalchemy import text

# Connect and drop alembic_version
with engine.connect() as conn:
    try:
        conn.execute(text("DROP TABLE alembic_version"))
        conn.commit()
        print("Dropped alembic_version table successfully.")
    except Exception as e:
        print(f"Error (might be okay if table didn't exist): {e}")
