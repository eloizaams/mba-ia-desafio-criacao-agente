# Plano de implementação — Assistente Residencial Aurora

> Documento vivo. Ponto de retomada entre sessões: leia a seção **Status** primeiro.

## Status
- [x] Fase 0 — Decisões de alto nível (este documento)
- [x] Fase 1 — Setup do projeto (`feature/setup`): ADK fixado em `2.11.0` (mais recente da série 2 no PyPI), `uv.lock` gerado, ruff/mypy/pytest/pre-commit configurados, CI em `.github/workflows/ci.yml`. Commit pendente (ver conversa).
- [ ] Fase 2 — Spike ADK: confirmação + sessão persistida (`spike/adk-confirmacao`, descartável)
- [ ] Fase 3 — Domínio + persistência + restauração (`feature/dominio-persistencia`)
- [ ] Fase 4 — Tools + agentes (`feature/agentes`)
- [ ] Fase 5 — API (`feature/api`)
- [ ] Fase 6 — Concorrência e hardening das garantias (`feature/garantias`)
- [ ] Fase 7 — E2E do avaliador, README final, release `v1.0.0`

## Decisões (ADR resumido)
| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D1 | Linguagem | Python 3.12+ / uv | Obrigatório no enunciado |
| D2 | Armazenamento | SQLite (dados + sessões ADK via `DatabaseSessionService` `sqlite+aiosqlite`) | Zero infra; constraint garante exclusividade; enunciado validou confirmação com SQLite |
| D3 | Arquitetura | Hexagonal leve: `domain/`, `application/`, `adapters/` (adk, api, persistence) | Garantias testáveis sem LLM; tools finas |
| D4 | Topologia | Root → `reservas` e `visitantes` como `sub_agents`; `regulamento` como `AgentTool` | Confirmação retoma no agente que pediu; regulamento em contexto isolado (Garantia 4) |
| D5 | Confirmação | Nativa ADK (`require_confirmation`) + guarda em código na rota (409) | Conceito avaliado; guarda impede id inválido/repetido |
| D6 | Qualidade | pytest (unit + concorrência), script E2E do avaliador, ruff + mypy + pre-commit, CI | Portfólio |
| D7 | SDD | Próprio enxuto: `docs/constitution.md` + `docs/specs/NNN-nome/{spec,plan,tasks}.md` | Leve e rastreável |
| D8 | Git | Git Flow completo, tag `v1.0.0` na `main` | Disciplina de entrega; `main` = entregável |
| D9 | Idioma | Domínio PT, infra EN | Casa com o contrato da API |
| D10 | Modelo | Tier pago; modelos definidos no spike (consultar doc oficial) | Modelos mudam com frequência |

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

### Fase 2 — Spike (maior risco)
Validar em código descartável, com sessão SQLite persistida:
1. Tool com `require_confirmation` dentro de um `sub_agent` gera `adk_request_confirmation`.
2. Retomar via Runner enviando `FunctionResponse` de `adk_request_confirmation` — aprovar executa uma vez; negar não executa.
3. Repetir 1–2 **após reiniciar o processo**.
4. Qual config faz a resposta chegar ao agente certo (transferências, `ResumabilityConfig` do App).
5. Se eventos internos de `AgentTool` entram ou não na sessão pai (Garantia 4).
6. Modelos Gemini disponíveis e escolha por agente.
Saída: skill/nota `adk-confirmacao` com o padrão comprovado + registro no `DESAFIOS.md`.

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
