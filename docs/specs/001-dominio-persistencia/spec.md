# Spec 001 — Domínio e persistência

Fase 3 de [`docs/PLANO.md`](../../PLANO.md). Garantias e passos do avaliador cobertos: G1 (base da cobrança), G3 (reinício), G5 (exclusividade), passo 15 (exclusividade no instante da gravação).

## Escopo

1. Entidades e regras de negócio em `domain/`, sem ADK, FastAPI nem SQLite.
2. Portas (interfaces de repositório) em `application/`, para a camada de cima depender de abstração.
3. Adaptador SQLite em `adapters/persistence/`: schema, repositórios e tradução de erro de constraint em resultado de domínio.
4. `aurora-restore`: volta reservas ativas e visitantes ao estado de `dados/*.json`.
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
- **Colisão de código esgotada:** após 5 tentativas, `gravar_reserva` levanta `RuntimeError`. Não é `DominioError`, porque não é regra de negócio, e a chance é desprezível. Antes da Fase 5 ele precisa virar erro controlado; não pode sair como 500 cru (`PLANO.md`, Fase 5).
- **Erro de constraint:** o adaptador distingue os dois `UNIQUE` pela mensagem do SQLite. Índice da agenda vira `DataIndisponivel` (domínio). Colisão de código gera novo código e tenta de novo, com limite.
- **Restore e histórico:** o restore apaga só as reservas ativas e recarrega as do seed. Reservas canceladas fora do seed ficam como histórico, para que o código nunca seja reaproveitado (regra 5). Reserva do seed que foi cancelada volta a ativa com o mesmo código, porque é estado inicial, não reserva nova. Áreas e apartamentos são upsert, porque reservas canceladas os referenciam por FK. Esse desvio do enunciado ("volta ao estado desses arquivos") é decisão registrada aqui: as tabelas de reservas não ficam idênticas aos JSON depois de canceladas.
  Consequência: a regra 5 cobre só as canceladas. Códigos de reservas ativas que o restore remove (criadas na conversa) podem voltar a ser gerados. Aceito como efeito de reset.
  Para o README (Fase 7): repetir este desvio junto da seção de Garantias, porque o enunciado exige a explicação.
- **Acesso a dados:** `sqlite3` da biblioteca padrão, conexão curta por operação, `busy_timeout` para que escritas concorrentes aguardem em vez de falhar, WAL para leitura concorrente.

## Critérios de aceite

- Duas gravações simultâneas na mesma área e data: exatamente uma vence, a outra vira `DataIndisponivel`, nenhuma exceção vaza.
- Sem a constraint, a checagem prévia deixa todas gravarem (teste de contraste).
- Cancelar reserva de outro apartamento não altera nada e devolve "não encontrada".
- `aurora-restore` deixa reservas ativas e visitantes idênticos aos JSON de `dados/`. Rodar duas vezes produz o mesmo banco, inclusive os ids dos visitantes.
- `domain/` e `application/` passam em `mypy` strict com `disallow_any_explicit`.
