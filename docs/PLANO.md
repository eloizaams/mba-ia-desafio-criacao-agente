# Plano de implementação — Assistente Residencial Aurora

> Documento vivo. Ponto de retomada entre sessões: leia a seção **Status** primeiro.

## Status
- [x] Fase 0 — Decisões de alto nível (este documento)
- [x] Fase 1 — Setup do projeto (`feature/setup`): ADK fixado em `2.11.0` (mais recente da série 2 no PyPI), `uv.lock` gerado, ruff/mypy/pytest/pre-commit configurados, CI em `.github/workflows/ci.yml`.
- [x] Fase 2 — Spike ADK (`spike/adk-confirmacao`): padrão de confirmação/retomada comprovado em execução, sem chave de API. Resultados em [`docs/ADK-CONFIRMACAO.md`](ADK-CONFIRMACAO.md); frições em [`DESAFIOS.md`](../DESAFIOS.md).
- [ ] Fase 3 — Domínio + persistência + restauração (`feature/dominio-persistencia`)
- [ ] Fase 4 — Tools + agentes (`feature/agentes`)
- [ ] Fase 5 — API (`feature/api`)
- [ ] Fase 6 — Concorrência e hardening das garantias (`feature/garantias`)
- [ ] Fase 7 — E2E do avaliador, README final, release `v1.0.0`

## Decisões (ADR resumido)
| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D1 | Linguagem | Python 3.12+ / uv | Obrigatório no enunciado |
| D2 | Armazenamento | SQLite: dados do condomínio + sessões ADK via **`SqliteSessionService`** | Zero infra; constraint garante exclusividade. Revisado na Fase 2: `DatabaseSessionService` exige o extra `[db]` (SQLAlchemy); `SqliteSessionService` usa só `aiosqlite` e é o que o CLI do ADK usa |
| D3 | Arquitetura | Hexagonal leve: `domain/`, `application/`, `adapters/` (adk, api, persistence) | Garantias testáveis sem LLM; tools finas |
| D4 | Topologia | Root → `reservas` e `visitantes` como `sub_agents` (**transferência livre**); `regulamento` como `AgentTool` | Comprovado na Fase 2: confirmação retoma no agente que pediu; `AgentTool` isola o contexto por construção (Garantia 4). Travar o sub-agente com `disallow_transfer_to_*` quebra a retomada |
| D5 | Confirmação | Nativa ADK (`require_confirmation`) + `App(resumability_config=ResumabilityConfig(is_resumable=True))` + guarda em código na rota (409) | Conceito avaliado; guarda impede id inválido/repetido. `is_resumable` deixa o roteamento da resposta explícito |
| D6 | Qualidade | pytest (unit + concorrência), script E2E do avaliador, ruff + mypy + pre-commit, CI | Portfólio |
| D7 | SDD | Próprio enxuto: `docs/constitution.md` + `docs/specs/NNN-nome/{spec,plan,tasks}.md` | Leve e rastreável |
| D8 | Git | Git Flow completo, tag `v1.0.0` na `main` | Disciplina de entrega; `main` = entregável |
| D9 | Idioma | Domínio PT, infra EN | Casa com o contrato da API |
| D10 | Modelo | `gemini-3.8-flash` nos dois papéis | Definido na Fase 2: Flash estável mais recente (out/2026). Pro só existe em preview; a série 2.5 dos exemplos do ADK está legada |
| D11 | Teste sem LLM | `ScriptedLlm` (subclasse de `BaseLlm`) reativo ao histórico | Fase 2: permite testar confirmação, retomada e persistência no CI sem `GOOGLE_API_KEY` |

## Estrutura alvo
```
src/aurora/
  domain/          # entidades, regras, erros (sem dependências)
  application/     # casos de uso: reservar, cancelar, autorizar visitante, consultar regulamento
  adapters/
    persistence/   # SQLite: schema, repositórios, seed/restore
    adk/           # tools, agentes, App/Runner, confirmação
    api/           # FastAPI: rotas, schemas, serialização de eventos
  config.py
scripts/           # e2e_avaliador.py
tests/             # unit/, integration/
docs/              # constitution.md, PLANO.md, specs/
```
Comandos (via `[project.scripts]`): `uv run aurora-api` (sobe em :8000), `uv run aurora-restore` (restaura dados; flag `--sessoes` para limpar sessões).

## Fases

### Fase 1 — Setup
- `pyproject.toml` (uv), ADK fixado na versão exata mais recente da série 2 (≥2.2.0), FastAPI, uvicorn, aiosqlite.
- ruff, mypy, pytest, pytest-asyncio, pre-commit; CI (lint + testes sem chave).
- `.env.example` (`GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE`, modelos, caminho do banco); `.gitignore` com `.env`, `*.db`.

### Fase 2 — Spike (maior risco) — concluída
Os seis pontos foram validados por execução, em `spike/`:
1. ✅ Pedido `adk_request_confirmation` gerado **pelo sub-agente**; tool não executa.
2. ✅ Aprovar executa uma vez; negar não executa.
3. ✅ Vale entre processos (cada subcomando do spike é um processo novo; só o SQLite atravessa).
4. ✅ `is_resumable=True` + sub-agente com transferência livre.
5. ✅ `AgentTool` não vaza eventos para a sessão do pai.
6. ✅ `gemini-3.8-flash`.

Saídas: [`docs/ADK-CONFIRMACAO.md`](ADK-CONFIRMACAO.md) (padrão comprovado),
[`DESAFIOS.md`](../DESAFIOS.md) (frições), `spike/` (código descartável, não vai para a `main`).

Pendente de chave: um *smoke test* com Gemini real, para confirmar que o modelo
de verdade produz o mesmo fluxo de eventos. A mecânica já está provada.

### Fase 3 — Domínio + persistência
- Tabelas: `areas`, `apartamentos`, `reservas(codigo UNIQUE, apartamento, area, data, status)`, índice único parcial `(area, data) WHERE status='ativa'`; `visitantes`.
- Cancelamento = `status='cancelada'` (código nunca é reaproveitado — regra 5). Código gerado pelo sistema, com retry em colisão.
- `IntegrityError` na gravação → resultado de domínio "data indisponível" (Garantia 5, sem 500).
- `aurora-restore` recria a partir de `dados/*.json`.
- Testes: unitários + concorrência (N gravações simultâneas → 1 vence).

### Fase 4 — Tools + agentes
- Tools leem apartamento de `tool_context.state` (gravado em `POST /sessoes`, chave não sobrescrevível pelo modelo).
- Reservas: `listar_minhas_reservas`, `verificar_disponibilidade(area, data)` → só `livre/ocupada`, `reservar(area, data)` (`require_confirmation` = callable que retorna `True` se taxa > 0), `cancelar_minha_reserva(...)` (filtra pelo apartamento da sessão; reserva alheia = "não encontrada").
- Visitantes: `listar_meus_visitantes`, `autorizar_visitante(nome, data)` (sempre confirma).
- Regulamento: `consultar_regulamento(topico)` → só o(s) capítulo(s) pertinente(s); agente `regulamento` como `AgentTool`.
- Root: roteia, sem regulamento nas instruções.

### Fase 5 — API
- `POST /sessoes` (201), `POST /sessoes/{id}/mensagens`, `POST /sessoes/{id}/confirmacoes` (409 se id não pendente), `GET /sessoes/{id}/eventos`, `GET /apartamentos/{n}/reservas|visitantes`. 404 para sessão inexistente.
- `confirmacoes_pendentes` derivadas dos eventos da sessão (pedidos sem resposta).

### Fase 6 — Hardening
- Revisão adversarial das 5 garantias (prompt injection, vazamento em mensagens de erro, "302 isolado").
- Teste de disputa concorrente pela API (passo 14).

### Fase 7 — Entrega
- `scripts/e2e_avaliador.py` reproduzindo os passos 1–14 (incl. reinício).
- README: Arquitetura, Garantias (arquivo + trecho), Como rodar.
- `release/v1.0.0` → `main` + tag; conferir `dados/` idêntico ao base (`git diff be87e1d -- dados/`).

## Rastreabilidade garantias → fases
| Garantia | Fases | Passos do avaliador |
|---|---|---|
| G1 Confirmação | 2, 4, 5 | 6, 7, 8, 9, 11 |
| G2 Sessão = apartamento | 4, 6 | 3, 4, 5, 10 |
| G3 Reinício | 2, 3, 5 | 13 |
| G4 Regulamento | 2, 4 | 12 |
| G5 Concorrência | 3, 6 | 14 |
