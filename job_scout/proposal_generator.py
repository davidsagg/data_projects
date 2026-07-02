import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROPOSAL_SYSTEM = '''
Você escreve propostas no Freelancer.com para um dev Python sênior (conta nova).
Regras: máx 150 palavras · inglês · começa pelo problema real do cliente
· menciona abordagem técnica concreta · termina com pergunta de engajamento
· tom direto e humano, sem buzzwords.
Para nicho music_automation: mencione experiência com banda/streaming.
Para nicho music_production: tom de músico para músico, mencione DAW
e referências sonoras concretas; nada de jargão de software.
Para nicho no_tech_automation: use 'you don't need to know any code'.
Retorne APENAS a proposta em texto puro.
'''

def generate_proposal(job: dict, score_data: dict) -> str:
    prompt = (
        f"Job: {job['title']}\n"
        f"Descrição: {job['description']}\n"
        f"Budget: {job['budget']}\n"
        f"Nicho: {score_data.get('detected_niche', job['niche'])}\n"
        f"Complexidade: {score_data['complexity']} (~{score_data['estimated_hours']}h)\n"
    )
    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=400,
        system=PROPOSAL_SYSTEM,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response.content[0].text.strip()
