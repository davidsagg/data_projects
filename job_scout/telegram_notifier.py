import logging
import re
import httpx
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)

# Legacy Markdown only treats _ * ` [ as special.
_MD_ESCAPE = re.compile(r'([_*`\[])')

def escape_md(text: str) -> str:
    return _MD_ESCAPE.sub(r'\\\1', text or '')

def _post(payload: dict) -> httpx.Response:
    return httpx.post(
        f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
        json=payload,
        timeout=10,
    )

def send_job_notification(job: dict, score_data: dict, proposal: str):
    score = score_data['score']
    complexity = score_data['complexity']
    hours = score_data['estimated_hours']
    flags = score_data.get('red_flags', [])
    niche = score_data.get('detected_niche', job['niche'])

    emoji = '🔥🔥' if score >= 9 else '🔥' if score >= 7 else '✅'
    niche_icon = {'music_automation':'🎸','music_production':'🎚️',
                  'analytics_consulting':'📊','no_tech_automation':'⚙️'}.get(niche, '💼')

    title_md   = escape_md(job['title'])
    just_md    = escape_md(score_data['justification'])
    budget_md  = escape_md(str(job['budget']))
    flags_text = (
        chr(10).join(f'  ⚠️ {escape_md(f)}' for f in flags) if flags else '  Nenhum'
    )

    message = (
        f"{emoji} *SCORE {score}/10*  |  {niche_icon} `{niche}`\n"
        f"\n*{title_md}*\n"
        f"💰 Budget: ${budget_md}\n"
        f"⏱ {complexity} · ~{hours}h estimado\n"
        f"\n💡 _{just_md}_\n"
        f"\n📝 *Rascunho de proposta:*\n"
        f"```\n{proposal}\n```\n"
        f"\n⚠️ *Red flags:*\n{flags_text}\n"
        f"\n🔗 [Ver vaga no Freelancer.com]({job['url']})"
    ).strip()

    base = {'chat_id': TELEGRAM_CHAT_ID, 'disable_web_page_preview': False}
    resp = _post({**base, 'text': message, 'parse_mode': 'Markdown'})

    # Fallback: se o Markdown quebrou no parse do Telegram, reenvia em texto puro
    # para não perder a notificação por causa de um caractere especial no título.
    if resp.status_code == 400 and 'parse' in resp.text.lower():
        log.warning(f'Markdown rejeitado pelo Telegram, reenviando em texto puro: {resp.text}')
        plain = re.sub(r'[\\*_`\[\]]', '', message)
        resp = _post({**base, 'text': plain})

    resp.raise_for_status()
