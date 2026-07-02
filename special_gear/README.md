# 🎸 Special Gear Monitor

Monitor automático de leilões da Receita Federal do Brasil em busca de instrumentos musicais e equipamentos de áudio com boa relação custo-benefício.

---

## Como funciona

1. Verifica diariamente as regiões fiscais configuradas em `config.py`
2. Baixa e parseia os editais (PDF ou HTML)
3. Filtra lotes por palavras-chave (guitarra, pedal, amplificador…)
4. Busca preços de referência no Mercado Livre, Two Tone Guitars e High Voltage Custom Shop
5. Calcula o spread entre preço de mercado e lance mínimo
6. Envia alertas via Telegram com os lotes mais interessantes (spread ≥ `SPREAD_MINIMO`)

---

## Pré-requisitos

- Python 3.11+
- Bot Telegram (criado via @BotFather — nenhuma conta de email necessária)

---

## Instalação

```bash
# Clone ou baixe o projeto
cd data_projects/special_gear

# Crie e ative um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

---

## Configuração

### 1. Copiar o arquivo de variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais Telegram:

```
TELEGRAM_BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
```

### 2. Como configurar o bot Telegram (5 minutos)

1. No Telegram, fale com **@BotFather** → `/newbot` → escolha um nome → copie o token
2. Mande qualquer mensagem para o bot que você criou
3. Acesse no navegador: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Localize o campo `"chat": {"id": <número>}` — esse é o seu `TELEGRAM_CHAT_ID`
5. Cole os dois valores no `.env`

> Nenhuma senha é armazenada no código. O token fica apenas no `.env` (não versionado).

---

## Como testar

Execute um ciclo único sem agendamento:

```bash
python main.py --test
```

O monitor busca editais, parseia, filtra, busca preços e (se encontrar oportunidades) envia o alerta via Telegram.

---

## Execução contínua (manual)

```bash
python main.py
```

Roda um ciclo imediatamente e agenda novos ciclos diariamente às **08:00**.
Pressione `Ctrl+C` para encerrar.

---

## Instalação como serviço no macOS (launchd)

Para que o monitor inicie automaticamente ao fazer login:

```bash
# 1. Descobrir o caminho do Python
which python3

# 2. Editar o plist se necessário (ajustar o caminho do Python)
nano com.dave.monitor.plist

# 3. Copiar para LaunchAgents
cp com.dave.monitor.plist ~/Library/LaunchAgents/

# 4. Carregar o serviço
launchctl load ~/Library/LaunchAgents/com.dave.monitor.plist

# 5. Verificar se está rodando
launchctl list | grep special_gear

# 6. Ver os logs
tail -f ~/Library/Logs/special_gear_monitor.log
```

Para desinstalar:

```bash
launchctl unload ~/Library/LaunchAgents/com.dave.monitor.plist
rm ~/Library/LaunchAgents/com.dave.monitor.plist
```

---

## Como adicionar palavras-chave

Edite `config.py` e adicione termos ao dicionário `KEYWORDS`:

```python
KEYWORDS = {
    "guitarra": ["guitarra", "stratocaster", "telecaster", "les paul", "sg"],
    "pedal":    ["pedal", "overdrive", "delay", "reverb", "fuzz"],
    "amp":      ["amplificador", "combo", "cabeçote", "marshall", "fender"],
    "baixo":    ["baixo", "precision", "jazz bass"],   # ← novo nicho
}
```

---

## Como adicionar regiões

Edite `config.py` e adicione URLs ao dicionário `REGIOES`:

```python
REGIOES = {
    "8RF_SP": "https://www.rfb.gov.br/leiloes/8rf",
    "7RF_RJ": "https://www.rfb.gov.br/leiloes/7rf",
    "4RF_PR": "https://www.rfb.gov.br/leiloes/4rf",
    "1RF_AM": "https://www.rfb.gov.br/leiloes/1rf",  # ← nova região
}
```

---

## Estrutura do projeto

```
special_gear/
├── config.py                   # Regiões, keywords e parâmetros
├── main.py                     # Orquestrador principal
├── requirements.txt            # Dependências Python
├── .env.example                # Template de variáveis de ambiente
├── com.dave.monitor.plist      # Serviço launchd para macOS
├── README.md                   # Esta documentação
├── alertas/
│   ├── __init__.py
│   └── telegram_sender.py      # Cards formatados e envio via Telegram Bot API
├── scraper/
│   ├── receita_federal.py      # Busca e parse de editais da RF
│   └── precos.py               # Busca de preços de referência (ML, TwoTone, HV)
└── data/
    └── leiloes.db              # SQLite — controle de lotes já processados
```

---

## Parâmetros principais (`config.py`)

| Parâmetro       | Padrão | Descrição                                      |
|-----------------|--------|------------------------------------------------|
| `SPREAD_MINIMO` | 1.5    | Spread mínimo (preço_ref / lance) para alertar |
| `REGIOES`       | 3 regiões | URLs das superintendências da RF             |
| `KEYWORDS`      | 3 nichos | Termos por categoria de instrumento           |

---

## Score dos lotes no alerta Telegram

| Score | Critério |
|-------|----------|
| 🟢 **ALTO** | spread ≥ 2.5x + nicho identificado + lote simples (não misto) |
| 🟡 **MÉDIO** | spread ≥ 1.5x e descrição clara |
| 🔴 **BAIXO** | spread ≥ 1.5x mas descrição vaga ou lote com múltiplos itens |
