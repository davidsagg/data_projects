# ADR-001: Mercado Bitcoin como exchange principal

**Status:** Aceito  
**Data:** 2026-05-12  
**Autores:** David Saggioro

---

## Contexto

O projeto opera com capital em BRL e precisa de uma exchange que:
- Permita depósitos, saques e operações diretamente em reais
- Disponibilize API pública e autenticada para leitura de portfólio e histórico de trades
- Seja regulamentada no Brasil (CNPJ, cumprimento CVM/BCB)
- Facilite o rastreamento mensal de vendas em BRL para fins de isenção fiscal (IN RFB 2.312/2026)

As alternativas consideradas foram Binance BR (encerrada), Foxbit, Coinext e NovaDAX.

---

## Decisão

Usar **Mercado Bitcoin** como exchange exclusiva para todas as operações de swing trading.

---

## Racional

| Critério                        | Mercado Bitcoin | Foxbit     | NovaDAX   |
|---------------------------------|-----------------|------------|-----------|
| Volume diário BTC/BRL           | ~R$250M (líder) | ~R$30M     | ~R$20M    |
| API pública documentada         | Sim (v4)        | Sim        | Sim       |
| API de trade autenticada        | Sim (TAPI)      | Sim        | Sim       |
| Pares disponíveis               | BTC, ETH, SOL + ~300 | ~80   | ~120      |
| Regulamentação BR               | Sim (CVM 188)   | Sim        | Sim       |
| Liquidez para swing trading     | Alta            | Média      | Baixa     |

O Mercado Bitcoin possui a maior liquidez do mercado brasileiro, minimizando slippage em ordens de swing trading. Sua API v4 + TAPI cobrem todos os casos de uso: leitura de saldo, histórico de trades e consulta de livro de ordens.

---

## Consequências

- **Positivas:** Liquidez superior, menor spread, API bem documentada, suporte nativo a BRL, facilita rastreamento fiscal por exchange
- **Negativas:** Taxas de saque BRL podem ser superiores a exchanges internacionais; pares de altcoins menos líquidos que Binance global
- **Mitigações:** Para ativos sem liquidez adequada no MB, monitorar via CoinGecko e apontar o usuário para execução manual; o Tax Optimizer rastreia vendas por exchange isoladamente

---

## Referências

- [API Mercado Bitcoin v4](https://api.mercadobitcoin.net/api/v4/doc)
- [IN RFB 2.312/2026](https://www.in.gov.br/) — isenção mensal por exchange
