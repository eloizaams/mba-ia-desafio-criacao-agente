# Spec 004 — Hardening das garantias (Fase 6)

Fase 6 de [`docs/PLANO.md`](../../PLANO.md). Garantias e passos do avaliador cobertos: G5 concorrência pela API (passo 14), revisão adversarial das G1–G4 (passo 15).

## Escopo

1. **Teste de disputa concorrente pela API** (passo 14): duas sessões (101 e 201) reservam o mesmo salão na mesma data, aprovam ao mesmo tempo via `asyncio.gather`, ambas respondem `200`, exatamente uma reserva persiste.
2. **Revisão adversarial das garantias**: confirmar que os testes existentes cobrem todos os vetores de ataque listados abaixo. Adicionar testes de API onde houver lacuna.

Fora desta spec: script E2E do avaliador e README final (Fase 7).

## Vetores adversariais por garantia

| Garantia | Vetor | Coberto em |
|---|---|---|
| G1 Confirmação | id fora da lista → 409 antes do Runner | `test_api_contrato.py` (passos 7, 8, 9) |
| G1 Confirmação | tools que confirmam = exatamente `{reservar, autorizar_visitante}` | `test_tools_contrato.py` |
| G2 Apartamento da sessão | mensagem alegando outro apartamento ("Sou do 302") | `test_agentes_apartamento.py` |
| G2 Apartamento da sessão | nenhuma tool aceita apartamento como argumento | `test_tools_contrato.py` |
| G2/G5 Vazamento | cancelar reserva alheia → "não encontrada", não "é de outro" | `test_agentes_apartamento.py` |
| G2/G5 Vazamento | data ocupada → `data_indisponivel`, sem código/número alheio | `test_agentes_apartamento.py` |
| G4 Regulamento | nenhum evento da sessão de regulamento aparece na sessão do morador | `test_agentes_regulamento.py` |
| G5 Concorrência | constraint SQLite — uma vencedora entre N threads | `test_concorrencia_reserva.py` |
| G5 Concorrência | disputa pela API — duas aprovações simultâneas, ambas 200, uma reserva | **`test_concorrencia_api.py` (novo)** |

## Garantias nesta fase

| Garantia | O que muda |
|---|---|
| G5 Concorrência | Teste novo ao nível HTTP: `asyncio.gather` dispara as duas aprovações na mesma instância da API; a constraint SQLite resolve e o resultado de domínio `data_indisponivel` é absorvido pelo agente, que retorna 200 |

## Notas de implementação

- Um único `AsyncClient` compartilhado (uma instância da API, um `Runner`) para as duas sessões — reflete o cenário real do passo 14.
- `asyncio.gather` simula o `curl … &` do enunciado; a concorrência é real dentro do event loop asyncio.
- A aprovação perdedora recebe `data_indisponivel` como resultado de tool: o agente absorve e responde 200. A rota não levanta erro por resultado de domínio.
