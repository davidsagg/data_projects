# ADR-004: SQLite como gerenciador de estado

**Status:** Aceito  
**Data:** 2026-05-12  
**Autores:** David Saggioro

---

## Contexto

O sistema precisa persistir:
- Portfólio atual (posições abertas)
- Recomendações geradas + status de aprovação human-in-the-loop
- Histórico de trades importados da exchange
- Acumulador fiscal mensal (vendas BRL por exchange)
- Log de performance (win/loss, R-múltiplo)
- Snapshots de dados de mercado usados em cada análise

**Restrições do ambiente:**
- Runtime exclusivamente local (MacBook M2, sem infra cloud)
- Uso single-user, nunca concorrência multi-processo pesada
- Custo zero de infraestrutura
- Volume de dados pequeno: ~50 trades/mês, ~10 recomendações/semana

---

## Decisão

Usar **SQLite com WAL mode + foreign keys** via `sqlite3` (stdlib) para toda persistência de estado.

---

## Racional

| Critério                   | SQLite   | PostgreSQL (local) | JSON files |
|----------------------------|----------|--------------------|------------|
| Custo infra                | Zero     | Zero (Docker)      | Zero       |
| Configuração               | Nenhuma  | Docker + init.sql  | Nenhuma    |
| ACID                       | Sim (WAL)| Sim                | Não        |
| Queries ad-hoc             | Sim      | Sim                | Difícil    |
| Backup                     | cp 1 file| pg_dump            | cp dir     |
| Adequado ao volume         | Sim      | Sim (overkill)     | Frágil     |

O SQLite em WAL mode suporta leitura concorrente (Streamlit UI lendo enquanto scheduler escreve) sem bloqueios. Um único arquivo `.db` simplifica backup, versionamento e migração.

---

## Implementação

```python
conn = sqlite3.connect("./data/crypto_advisor.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")
```

O módulo `db/schema.py` centraliza o DDL e a função `init_db()`. Migrações futuras via scripts numerados em `db/migrations/`.

---

## Consequências

- **Positivas:** Zero setup, backup trivial (`cp crypto_advisor.db backup/`), compatível com qualquer ambiente Python sem dependência extra
- **Negativas:** Não escala para múltiplos usuários; sem tipo `DECIMAL` nativo (usar `REAL` com cuidado em cálculos monetários)
- **Mitigações:** Valores monetários armazenados como `REAL` com arredondamento a 2 casas na camada de repositório; revisitar se o projeto escalar para multi-usuário (migrar para PostgreSQL nesse caso)
