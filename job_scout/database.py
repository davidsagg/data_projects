import sqlite3
from config import DB_PATH

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id        TEXT PRIMARY KEY,
                title         TEXT,
                url           TEXT,
                budget        TEXT,
                description   TEXT,
                feed_label    TEXT,
                niche         TEXT,
                score         INTEGER,
                proposal_draft TEXT,
                status        TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def is_seen(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            'SELECT 1 FROM jobs WHERE job_id = ?', (job_id,)
        ).fetchone()
    return row is not None

def save_job(job: dict):
    with get_conn() as conn:
        conn.execute('''
            INSERT OR IGNORE INTO jobs
            (job_id, title, url, budget, description, feed_label,
             niche, score, proposal_draft, status)
            VALUES (:job_id, :title, :url, :budget, :description,
                    :feed_label, :niche, :score, :proposal_draft, :status)
        ''', job)
        conn.commit()
