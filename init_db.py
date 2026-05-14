from database import engine, SessionLocal
from models import Base, Category, User, Chatbot, Lead, TrainingSource, Subscription, Transaction, Availability, Meeting
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

Base.metadata.create_all(bind=engine)
print("[OK] Database & tables created!")

# ── Safe column migrations for PostgreSQL (Supabase) ─────────────────────────────
# PostgreSQL supports ADD COLUMN IF NOT EXISTS natively.
migrations = [
    ("subscriptions", "trial_ends_at",       "TIMESTAMP"),
    ("subscriptions", "cancel_at_period_end", "INTEGER DEFAULT 0"),
    ("transactions",  "description",          "TEXT"),
]

with engine.connect() as conn:
    for table, column, col_type in migrations:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"))
            print(f"[MIGRATION] Ensured column {table}.{column} exists.")
        except ProgrammingError as e:
            print(f"[MIGRATION WARNING] {e}")
        except Exception as e:
            print(f"[MIGRATION ERROR] {e}")
    conn.commit()

# Seed categories
db = SessionLocal()
try:
    existing = db.query(Category).count()
    if existing == 0:
        db.add(Category(name="Real Estate", slug="real_estate"))
        db.add(Category(name="Freelancer / Agency", slug="freelancer_agency"))
        db.commit()
        print("[OK] Categories seeded!")
    else:
        print("[INFO] Categories already exist, skipping seed.")
finally:
    db.close()