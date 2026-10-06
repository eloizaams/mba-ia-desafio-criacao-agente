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

Fases 1–7 implementadas (PR #7 mergeado em `develop`). 110+ testes passam sem chave de API. `scripts/e2e_avaliador.py` reproduz o fluxo do avaliador contra a API no ar. Pendente: E2E com Gemini real num clone limpo e release `v1.0.0` (`release/*` → `main`, com tag). Revisão geral em `docs/REVISAO-ENTREGA.md`.

## Comandos extras

```bash
uv run aurora-restore                      # restaura dados iniciais
uv run aurora-restore --sessoes            # restaura dados + apaga sessões ADK
uv run aurora-api                          # sobe API em 127.0.0.1:8000 (lê .env)
```

## Arquitetura

Hexagonal leve em `src/aurora/`: `domain/` (entidades e regras, sem ADK, FastAPI nem SQLite), `application/` (casos de uso: reservar, cancelar, autorizar visitante, consultar regulamento), `adapters/` (`persistence/` SQLite, `adk/` tools, agentes e confirmação, `api/` FastAPI). `domain/` e `application/` são mypy strict com `disallow_any_explicit`.

Decisões que atravessam vários arquivos e não se descobrem lendo um só:

1. **Apartamento vem da sessão.** `criar_sessao` (em `adapters/adk/sessoes.py`) grava o apartamento em `state`; as tools leem dali, por `apartamento_da_sessao`, e nenhuma tem parâmetro de apartamento. O `user_id` do ADK é fixo (`"morador"`), para que a sessão seja localizável só pelo `session_id` que as rotas recebem.
2. **Topologia de agentes.** O root roteia. `reservas` e `visitantes` são `sub_agents` com transferência livre. Não use `disallow_transfer_to_parent` nem `disallow_transfer_to_peers` nos especialistas: a retomada de confirmação falha em silêncio. `regulamento` é `AgentTool`, que roda em sessão própria e não vaza eventos para a sessão do pai (Garantia 4). O root não recebe o regulamento nas instruções.
3. **Confirmação.** Tool com `require_confirmation` gera o evento `adk_request_confirmation` — callable (taxa > 0) em `reservar`, `True` em `autorizar_visitante`; o callable tem a mesma assinatura da tool. `pendentes()` (em `adapters/adk/confirmacoes.py`) deriva as pendências dos eventos da sessão (call sem function response de mesmo id), sem estado extra, e `acao`/`detalhes` saem do `originalFunctionCall`. `POST /confirmacoes` envia um `FunctionResponse` com esse id pelo Runner, **depois** de checar a pendência: id fora da lista levanta `ValueError` no Runner, então o 409 vem antes. O App usa `ResumabilityConfig(is_resumable=True)`. Detalhes em `docs/ADK-CONFIRMACAO.md`.
4. **Persistência.** SQLite, com sessões ADK via `SqliteSessionService`. `DatabaseSessionService` exige o extra `[db]` (SQLAlchemy), que o projeto não instala. A exclusividade de reserva é uma constraint: índice único parcial `(area, data) WHERE status='ativa'`. O `IntegrityError` na gravação vira resultado de domínio "data indisponível", nunca 500. Cancelamento marca `status='cancelada'`, e o código de reserva nunca é reaproveitado.
5. **`dados/` é somente leitura** (constituição 8). `aurora-restore` recria o banco a partir dos JSON; as mudanças da conversa vão para o banco.
6. **Modelos.** `gemini-3.5-flash-lite` nos dois papéis, por variáveis `AURORA_MODELO_*`; `gemini-3.5-flash` é a alternativa. 503 de alta demanda se resolve trocando a variável, não o código. `construir_raiz`/`construir_runner` recebem uma **fábrica** de modelo por nome de agente, e não um modelo: é o que permite uma instância de `ScriptedLlm` por agente nos testes. O `ScriptedLlm` (`tests/support/scripted_llm.py`) decide o turno a partir do histórico, não de um contador, e o roteiro é declarado pelo teste.
7. **Regulamento.** `consultar_regulamento(topico)` devolve no máximo dois capítulos, escolhidos em `domain/regulamento.py` por termos — título vale 10, corpo 1 — e um segundo capítulo só em quase-empate. Tópico sem casamento devolve só os títulos, para o agente tentar de novo. Nada disso depende do modelo.

## Convenções do projeto

- Git Flow: `feature/*` → `develop` → `release/*` → `main`, com tag na `main`. Conventional Commits. PR revisado com `code-review` antes do merge.
- Domínio em português (`Reserva`, `apartamento`); termos técnicos e infra em inglês (`repository`, `service`).
- Cada spec em `docs/specs/NNN-nome/` referencia as garantias e os passos do avaliador que cobre (constituição 9).
