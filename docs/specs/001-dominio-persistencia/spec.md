# Spec 001 — Domínio e persistência

Fase 3 de [`docs/PLANO.md`](../../PLANO.md). Garantias e passos do avaliador cobertos: G1 (base da cobrança), G3 (reinício), G5 (exclusividade), passo 15 (exclusividade no instante da gravação).

## Escopo

1. Entidades e regras de negócio em `domain/`, sem ADK, FastAPI nem SQLite.
2. Portas (interfaces de repositório) em `application/`, para a camada de cima depender de abstração.
3. Adaptador SQLite em `adapters/persistence/`: schema, repositórios e tradução de erro de constraint em resultado de domínio.
4. `aurora-restore`: recria reservas e visitantes a partir de `dados/*.json`.
5. Testes unitários (domínio) e de integração (SQLite real em arquivo temporário), incluindo a disputa concorrente.

Fora desta spec: tools, agentes, casos de uso que chamam o modelo (Fase 4), API (Fase 5), limpeza de sessões ADK do `aurora-restore --sessoes` (decidir na Fase 5, quando o schema de sessões estiver em uso pela API).

## Regras de negócio cobertas

| # | Regra | Onde fica |
|---|---|---|
| 1 | No máximo uma reserva ativa por área e data | Índice único parcial `(area, data) WHERE status='ativa'` (constraint) |
| 2 | Taxa > 0 gera cobrança | `Area.gera_cobranca` (domínio) |
| 3 | Visitante tem nome e data | `Visitante` (domínio) |
| 4 | Morador cancela só as próprias reservas | `cancelar` filtra por apartamento no `UPDATE` |
| 5 | Código novo nunca repete, nem de cancelada | `UNIQUE(codigo)` + geração com nova tentativa em colisão |

## Decisões de design desta fase

- **Dinheiro:** `Decimal`, lido de `taxa` via `str`. Evita erro de ponto flutuante em comparação com zero.
- **Cancelamento:** `status='cancelada'`, nunca `DELETE`. Mantém o código reservado.
- **Erro de constraint:** o adaptador distingue os dois `UNIQUE` pela mensagem do SQLite. Índice da agenda vira `DataIndisponivel` (domínio). Colisão de código gera novo código e tenta de novo, com limite.
- **Acesso a dados:** `sqlite3` da biblioteca padrão, conexão curta por operação, `busy_timeout` para que escritas concorrentes aguardem em vez de falhar, WAL para leitura concorrente.

## Critérios de aceite

- Duas gravações simultâneas na mesma área e data: exatamente uma vence, a outra vira `DataIndisponivel`, nenhuma exceção vaza.
- Cancelar reserva de outro apartamento não altera nada e devolve "não encontrada".
- `aurora-restore` deixa as tabelas idênticas aos JSON de `dados/`, e rodar duas vezes dá o mesmo resultado.
- `domain/` e `application/` passam em `mypy` strict com `disallow_any_explicit`.
