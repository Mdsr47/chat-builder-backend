from database import engine, SessionLocal
from models import Base, Category, User, Chatbot, Lead, TrainingSource, Subscription, Transaction, Availability, Meeting
import sqlite3

Base.metadata.create_all(bind=engine)
print("[OK] Database & tables created!")

# ── Safe column migrations for SQLite ─────────────────────────────
# SQLite doesn't support ALTER TABLE ADD COLUMN IF EXISTS, so we try/ignore
db_path = "rag.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

migrations = [
    ("subscriptions", "trial_ends_at",       "DATETIME"),
    ("subscriptions", "cancel_at_period_end", "INTEGER DEFAULT 0"),
    ("transactions",  "description",          "TEXT"),
]

for table, column, col_type in migrations:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        print(f"[MIGRATION] Added column {table}.{column}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"[MIGRATION] Column {table}.{column} already exists, skipping.")
        else:
            print(f"[MIGRATION WARNING] {e}")

conn.commit()
conn.close()

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