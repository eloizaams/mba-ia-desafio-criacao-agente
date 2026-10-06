# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Antes de começar

- `docs/PLANO.md` (seção Status) diz em que fase o projeto está. `DESAFIOS.md` lista armadilhas já vividas.
- `docs/constitution.md` são as regras não negociáveis. Toda spec, plano e PR deve respeitá-las.
- `README.md` ainda é o enunciado do desafio, não a documentação do projeto. Ele será substituído na Fase 7 (ver Entregável em `docs/enunciado-original.md`).

## Comandos

Python 3.12 com uv. O ADK está fixado em `google-adk==2.11.0`; não suba a versão sem rerodar o spike antes (código na tag `spike-fase-2`).

```bash
uv sync                                    # instala o uv.lock
uv run ruff check                          # lint
uv run ruff format --check                 # formatação
uv run mypy                                # strict em src/aurora e tests
uv run pytest                              # suíte completa, sem chave de API
uv run pytest tests/test_setup.py::test_adk_fixado_na_versao_do_projeto   # um teste
uv run pre-commit run --all-files          # hooks fora do commit
```

- O CI (`.github/workflows/ci.yml`) roda exatamente `ruff check`, `ruff format --check`, `mypy` e `pytest`. Rode os quatro antes de abrir PR.
- Os hooks do pre-commit só valem neste clone depois de `uv run pre-commit install`.
- Chamadas reais ao Gemini precisam de `GOOGLE_API_KEY` no ambiente. O ADK, como biblioteca, não lê `.env` (só a CLI lê), então carregue com `set -a; source .env; set +a`.
- Comandos do spike: `docs/ADK-CONFIRMACAO.md` (código: `git worktree add ../aurora-spike spike-fase-2`). Com `AURORA_LLM=real` o spike usa o Gemini de verdade, com os `AURORA_MODELO_*` do ambiente, em vez do `ScriptedLlm`.

## Estado atual

Fase 2 concluída (spike na tag `spike-fase-2`, descartado da branch). `src/aurora/` ainda contém só `__init__.py`. A arquitetura abaixo é o alvo das Fases 3 a 5 (`docs/PLANO.md`), não código existente.

## Arquitetura alvo

Hexagonal leve em `src/aurora/`: `domain/` (entidades e regras, sem ADK, FastAPI nem SQLite), `application/` (casos de uso: reservar, cancelar, autorizar visitante, consultar regulamento), `adapters/` (`persistence/` SQLite, `adk/` tools, agentes e confirmação, `api/` FastAPI). `domain/` e `application/` são mypy strict com `disallow_any_explicit`.

Decisões que atravessam vários arquivos e não se descobrem lendo um só:

1. **Apartamento vem da sessão.** `POST /sessoes` grava o apartamento em `tool_context.state`. As tools leem dali e nenhuma aceita apartamento escolhido pelo modelo.
2. **Topologia de agentes.** O root roteia. `reservas` e `visitantes` são `sub_agents` com transferência livre. Não use `disallow_transfer_to_parent` nem `disallow_transfer_to_peers` nos especialistas: a retomada de confirmação falha em silêncio. `regulamento` é `AgentTool`, que roda em sessão própria e não vaza eventos para a sessão do pai (Garantia 4). O root não recebe o regulamento nas instruções.
3. **Confirmação.** Tool com `require_confirmation` gera o evento `adk_request_confirmation`. `confirmacoes_pendentes` é derivado dos eventos da sessão (call sem function response de mesmo id), sem estado extra. `POST /confirmacoes` envia um `FunctionResponse` com esse id pelo Runner, e a rota responde 409 se o id não estiver pendente. O App usa `ResumabilityConfig(is_resumable=True)`. Detalhes em `docs/ADK-CONFIRMACAO.md`.
4. **Persistência.** SQLite, com sessões ADK via `SqliteSessionService`. `DatabaseSessionService` exige o extra `[db]` (SQLAlchemy), que o projeto não instala. A exclusividade de reserva é uma constraint: índice único parcial `(area, data) WHERE status='ativa'`. O `IntegrityError` na gravação vira resultado de domínio "data indisponível", nunca 500. Cancelamento marca `status='cancelada'`, e o código de reserva nunca é reaproveitado.
5. **`dados/` é somente leitura** (constituição 8). `aurora-restore` recria o banco a partir dos JSON; as mudanças da conversa vão para o banco.
6. **Modelos.** `gemini-3.5-flash` nos dois papéis, por variáveis `AURORA_MODELO_*`. Os testes que não usam chave usam `tests/support/scripted_llm.py` (`ScriptedLlm`): ele decide o turno a partir do histórico, não de um contador.

## Convenções do projeto

- Git Flow: `feature/*` → `develop` → `release/*` → `main`, com tag na `main`. Conventional Commits. PR revisado com `code-review` antes do merge.
- Domínio em português (`Reserva`, `apartamento`); termos técnicos e infra em inglês (`repository`, `service`).
- Cada spec em `docs/specs/NNN-nome/` referencia as garantias e os passos do avaliador que cobre (constituição 9).
