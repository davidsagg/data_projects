import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, PROFILE_SUMMARY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SCORER_SYSTEM = f'''
Você avalia oportunidades freelance para este profissional:
{PROFILE_SUMMARY}

Retorne APENAS JSON válido (sem markdown, sem explicações):
{{
  "score": <int 0-10>,
  "justification": "<2 frases>",
  "complexity": "<low|medium|high>",
  "estimated_hours": <int>,
  "red_flags": ["<lista ou array vazio>"],
  "detected_niche": "<analytics_consulting|music_automation|music_production|no_tech_automation>"
}}

Score alto (7-10): descrição vaga, cliente sem maturidade técnica,
budget real pro escopo, solucionável com Python/Streamlit/APIs públicas
ou (para music_production) com produção/mix/mastering em DAW.
Score baixo (0-6): ML avançado exigido, budget irreal, stack incompatível,
ou (para music_production) exige gênero/instrumento muito específico
fora do escopo, presença física, ou equipamento de estúdio profissional.
'''

def score_job(job: dict) -> dict:
    prompt = (
        f"Título: {job['title']}\n"
        f"Descrição: {job['description']}\n"
        f"Budget: {job['budget']}\n"
        f"Nicho RSS: {job['niche']}\n"
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        system=SCORER_SYSTEM,
        messages=[{'role': 'user', 'content': prompt}]
    )
    text = response.content[0].text.strip()
    text = text.replace('```json', '').replace('```', '').strip()
    return json.loads(text)
