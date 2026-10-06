# Tarefas 003 — API

- [x] `adapters/adk/conversa.py`: `enviar` e `confirmar` devolvem `Turno(resposta, pendencias)`
- [x] `adapters/adk/eventos.py`: serialização igual à do `api_server` do ADK
- [x] `tests/support/conversa.py` usa o código de produção (sem duplicar os movimentos)
- [x] Teste pelo `Runner`: `resposta == ""` quando a execução para na confirmação
- [x] `ApartamentoRepository.existe` + `SqliteRepository.existe` + teste
- [x] `adapters/api/schemas.py` com os campos do contrato
- [x] `criar_api`: `POST /sessoes` (201 / 422), rotas de verificação (formato do contrato, só reservas ativas)
- [x] `criar_api`: `mensagens`, `confirmacoes` (409 antes do `Runner`), `eventos`; 404 antes de tudo
- [x] Handler `ServerError` / `ClientError` 429 → 503
- [x] Teste: contrato (passos 2, 6, 7, 8, 9, 11)
- [x] Teste: eventos completos, em ordem, sem autor `regulamento` (passo 12)
- [x] Teste: app novo sobre o mesmo banco — mesmos eventos, mensagem nova, aprovação de pendência anterior (passo 13)
- [x] Teste: `ServerError` vira 503
- [x] `main.py` + `aurora-api` em `[project.scripts]`; `python-dotenv` como dependência direta
- [x] `aurora-restore --sessoes` + teste
- [x] `ruff check`, `ruff format --check`, `mypy`, `pytest` verdes sem chave de API
- [x] Smoke com Gemini real pela API (curl, passos 2 a 13), resultado anotado aqui
- [x] `CLAUDE.md` (Estado atual, Comandos) e `docs/PLANO.md` (Status) atualizados

## Smoke — 2026-10-06 — `gemini-3.5-flash-lite`

Modelo usado: `gemini-3.5-flash-lite` (o `-flash` deu 503 ao iniciar — padrão do DESAFIOS.md;
troca de variável de ambiente resolveu sem alterar código).

| Passo | O que testou | Resultado |
|---|---|---|
| 1 | `GET /apartamentos/101/reservas` e `/302/visitantes` após `aurora-restore` | ✅ RSV-1377 e Marina Duarte |
| 2 | `POST /sessoes` apartamento existente → 201; inexistente → 422 | ✅ |
| 3 | `GET /sessoes/nao-existe/eventos` → 404 | ✅ |
| 4 | Consulta de regulamento (churrasqueira) — resposta em PT, pendências `[]` | ✅ |
| 5 | `GET /reservas` após regulamento — só seed, sem poluição | ✅ |
| 6 | Reservar quadra (sem taxa) — sem pendência, grava na hora | ✅ RSV-51BA57 |
| 7 | Reservar salão (com taxa) — `resposta == ""`, 1 pendência, sem reserva; negar → sem reserva | ✅ |
| 8 | Aprovar reserva salão → grava RSV-4D92AF; reenviar mesmo id → 409 | ✅ |
| 9 | `id` inexistente → 409, nenhuma reserva criada | ✅ |
| 10 | Sessão do 302 vê RSV-4821; "101" não aparece nos eventos do 302 | ✅ |
| 11 | Autorizar visitante → pendência; aprovar → Joana Ribeiro aparece em `/visitantes` | ✅ |
| 12 | 42 eventos, autores: `aurora`, `user`, `reservas`, `visitantes`; nenhum `regulamento` | ✅ |
| 13 | Reinício: 42 eventos sobrevivem; mensagem nova → 50; aprovação de pendência criada antes do reinício → 200 | ✅ |

Todos os 13 passos passaram. 503 do `-flash` corrigido com `AURORA_MODELO_*=gemini-3.5-flash-lite`.
