# Plano 003 — API

## Estrutura

```
src/aurora/
  application/
    ports.py                         # + ApartamentoRepository.existe(numero)
  adapters/
    persistence/
      sqlite.py                      # + existe() de apartamento
      restore.py                     # + --sessoes: apaga events, sessions, user_states, app_states
    adk/
      conversa.py                    # enviar(runner, id, texto) / confirmar(runner, id, pendencia, confirmado)
                                     #   -> Turno(resposta: str, pendencias: list[PendenciaConfirmacao])
      eventos.py                     # evento_para_json(event): model_dump(mode="json", by_alias=True, exclude_none=True)
    api/
      __init__.py
      schemas.py                     # NovaSessao, SessaoCriada, Mensagem, RespostaConfirmacao,
                                     #   Pendencia, RespostaConversa, ReservaApi, VisitanteApi
      app.py                         # criar_api(runner, reservas, visitantes, apartamentos) -> FastAPI
                                     #   rotas, 404/409/422, handler de ServerError/429 -> 503
      main.py                        # aurora-api: load_dotenv, lifespan com create_schema, uvicorn.run
tests/
  support/
    conversa.py                      # passa a reexportar/usar adapters/adk/conversa.py
  integration/
    test_api_contrato.py             # rotas, status e formato (passos 2, 6, 7, 8, 9, 11)
    test_api_eventos.py              # serialização, ordem, sem autor `regulamento` (passo 12)
    test_api_reinicio.py             # app novo sobre o mesmo banco (passo 13)
    test_restore.py                  # + --sessoes
```

`pyproject.toml`: `aurora-api = "aurora.adapters.api.main:main"` em `[project.scripts]`; `python-dotenv` em `dependencies`.

## Ordem de trabalho

1. `adapters/adk/conversa.py` e `eventos.py`, com teste pelo `Runner` (resposta vazia quando para em confirmação; pendências relidas da sessão). `tests/support/conversa.py` passa a usá-los.
2. Porta `ApartamentoRepository.existe` + `SqliteRepository.existe`, com teste de integração.
3. `schemas.py` e `criar_api` com as rotas de verificação e `POST /sessoes` (as que não passam pelo modelo).
4. Rotas de conversa: `mensagens`, `confirmacoes` (guarda do 409 antes do `Runner`), `eventos`, e o 404 comum.
5. Handler de `ServerError`/`ClientError` 429 → 503.
6. Testes da API: contrato, eventos, reinício.
7. `main.py` + script `aurora-api`; conferir à mão `uv run aurora-api` respondendo em `:8000`.
8. `aurora-restore --sessoes` + teste.
9. Smoke com Gemini real pela API (curl nos passos 2 a 13), anotado em `tasks.md`.
10. Atualizar `CLAUDE.md` (Estado atual, Comandos) e `docs/PLANO.md` (Status).

## Pontos de atenção

- **Guarda do 409 antes do `Runner`.** `id` fora de `pendentes()` levanta `ValueError` dentro do `Runner` e vira 500; id já respondido é aceito em silêncio e não reexecuta. A rota checa primeiro, sempre (`DESAFIOS.md`).
- **404 antes do `Runner`.** `run_async` com sessão inexistente também levanta. `buscar_sessao` primeiro, em toda rota com `{session_id}`.
- **`is_final_response()` e partes `thought`.** Modelos Gemini 3.x podem devolver `thought=True` em partes de texto; não entram em `resposta`.
- **Duas conexões no mesmo arquivo.** O repositório usa `sqlite3` síncrono e o `SqliteSessionService` usa `aiosqlite`, ambos no mesmo `.db`. O `timeout` padrão de 5 s do `sqlite3` cobre a espera por lock no fluxo sequencial; a disputa simultânea é teste da Fase 6, não desta.
- **`load_dotenv` só no `main`.** `criar_api` não lê ambiente: os testes não podem depender de um `.env` local.
- **`ScriptedLlm` com porta de saída.** Toda regra que emite function call precisa fechar em texto, senão estoura o limite de 500 chamadas (`DESAFIOS.md`).
- **Ordem de `ruff`:** `ruff format` depois `ruff check --fix`.
