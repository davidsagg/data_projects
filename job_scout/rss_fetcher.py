import feedparser
import hashlib
import re
import html
import logging
import yaml
from config import FEEDS_PATH, BUDGET_MIN, BUDGET_MAX

log = logging.getLogger(__name__)

HOURLY_PATTERN = re.compile(r'/\s*(hr|hour)\b|per\s+hour|hourly', re.IGNORECASE)

def load_feeds() -> list[dict]:
    with open(FEEDS_PATH) as f:
        data = yaml.safe_load(f)
    feeds = []
    for niche, items in data['feeds'].items():
        for item in items:
            feeds.append({'niche': niche, **item})
    return feeds

def is_hourly(text: str) -> bool:
    return bool(HOURLY_PATTERN.search(text))

def extract_budget(text: str) -> float | None:
    # Freelancer summary starts with "$XXX\nAverage bid" — match that first
    patterns = [
        r'^\$([0-9,]+)',
        r'\$([0-9,]+)',
        r'USD\s*([0-9,]+)',
        r'budget[:\s]+\$?([0-9,]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(',', ''))
    return None

def clean_html(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def make_job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def fetch_all_jobs() -> list[dict]:
    feeds = load_feeds()
    all_jobs = []
    seen_ids = set()
    skipped_hourly = skipped_no_budget = skipped_range = 0
    for feed_config in feeds:
        parsed = feedparser.parse(feed_config['url'])
        for entry in parsed.entries:
            url = entry.get('link', '')
            job_id = make_job_id(url)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = entry.get('title', '')
            raw_summary = entry.get('summary', '')

            if is_hourly(raw_summary):
                skipped_hourly += 1
                continue

            budget_value = extract_budget(raw_summary)
            if budget_value is None:
                skipped_no_budget += 1
                continue
            if not (BUDGET_MIN <= budget_value <= BUDGET_MAX):
                skipped_range += 1
                continue

            description = clean_html(raw_summary)
            all_jobs.append({
                'job_id':      job_id,
                'title':       title,
                'description': description[:2000],
                'url':         url,
                'budget':      str(budget_value),
                'feed_label':  feed_config['label'],
                'niche':       feed_config['niche'],
            })
    log.info(
        f'Filtros: {skipped_hourly} hourly, '
        f'{skipped_no_budget} sem budget, '
        f'{skipped_range} fora de ${BUDGET_MIN}-${BUDGET_MAX}'
    )
    return all_jobs
