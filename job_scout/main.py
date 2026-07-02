import logging
from database import init_db, is_seen, save_job
from rss_fetcher import fetch_all_jobs
from job_scorer import score_job
from proposal_generator import generate_proposal
from telegram_notifier import send_job_notification
from config import SCORE_THRESHOLD

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

def run_pipeline():
    init_db()
    log.info('🔍 Iniciando pipeline...')
    jobs = fetch_all_jobs()
    new_jobs = [j for j in jobs if not is_seen(j['job_id'])]
    log.info(f'📡 {len(jobs)} jobs | 🆕 {len(new_jobs)} novos')
    notified = 0
    for job in new_jobs:
        try:
            score_data = score_job(job)
            score = score_data['score']
            log.info(f'Score {score}/10 — {job["title"][:60]}')
            if score >= SCORE_THRESHOLD:
                proposal = generate_proposal(job, score_data)
                try:
                    send_job_notification(job, score_data, proposal)
                    status = 'notified'
                    notified += 1
                except Exception as e:
                    # Proposta já foi gerada (custo afundado) — preservar no DB
                    # mesmo se a notificação falhar, para retry manual.
                    log.error(f'Telegram falhou: {e}')
                    status = 'notify_failed'
            else:
                proposal, status = '', 'low_score'
            save_job({**job, 'score': score,
                      'proposal_draft': proposal, 'status': status})
        except Exception as e:
            log.error(f'Erro: {e}')
            save_job({**job, 'score': 0,
                      'proposal_draft': '', 'status': 'error'})
    log.info(f'✅ Concluído — {notified} notificações enviadas')

if __name__ == '__main__':
    log.info('🚀 Agent iniciado — execução única')
    run_pipeline()
