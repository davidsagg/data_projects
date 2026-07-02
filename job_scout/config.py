import os
from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_API_KEY  = os.getenv('ANTHROPIC_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')
SCORE_THRESHOLD    = int(os.getenv('SCORE_THRESHOLD', 7))
BUDGET_MIN         = int(os.getenv('BUDGET_MIN', 50))
BUDGET_MAX         = int(os.getenv('BUDGET_MAX', 500))
DB_PATH            = 'job_scout.db'
FEEDS_PATH         = 'feeds.yaml'
CLAUDE_MODEL       = 'claude-opus-4-5'

PROFILE_SUMMARY = (
  'Python developer, data scientist, experienced manager. '
  'Expert in dashboards (Streamlit/Plotly), data pipelines, '
  'Python automation, music data (Spotify API), sports analytics. '
  'Also a working musician and music producer: beat-making, '
  'mixing/mastering, and remote instrument recording sessions. '
  'New Freelancer.com account (no reviews yet). Targeting low-competition jobs.'
)
