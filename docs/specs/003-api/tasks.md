# Tarefas 003 — API

- [ ] `adapters/adk/conversa.py`: `enviar` e `confirmar` devolvem `Turno(resposta, pendencias)`
- [ ] `adapters/adk/eventos.py`: serialização igual à do `api_server` do ADK
- [ ] `tests/support/conversa.py` usa o código de produção (sem duplicar os movimentos)
- [ ] Teste pelo `Runner`: `resposta == ""` quando a execução para na confirmação
- [ ] `ApartamentoRepository.existe` + `SqliteRepository.existe` + teste
- [ ] `adapters/api/schemas.py` com os campos do contrato
- [ ] `criar_api`: `POST /sessoes` (201 / 422), rotas de verificação (formato do contrato, só reservas ativas)
- [ ] `criar_api`: `mensagens`, `confirmacoes` (409 antes do `Runner`), `eventos`; 404 antes de tudo
- [ ] Handler `ServerError` / `ClientError` 429 → 503
- [ ] Teste: contrato (passos 2, 6, 7, 8, 9, 11)
- [ ] Teste: eventos completos, em ordem, sem autor `regulamento` (passo 12)
- [ ] Teste: app novo sobre o mesmo banco — mesmos eventos, mensagem nova, aprovação de pendência anterior (passo 13)
- [ ] Teste: `ServerError` vira 503
- [ ] `main.py` + `aurora-api` em `[project.scripts]`; `python-dotenv` como dependência direta
- [ ] `aurora-restore --sessoes` + teste
- [ ] `ruff check`, `ruff format --check`, `mypy`, `pytest` verdes sem chave de API
- [ ] Smoke com Gemini real pela API (curl, passos 2 a 13), resultado anotado aqui
- [ ] `CLAUDE.md` (Estado atual, Comandos) e `docs/PLANO.md` (Status) atualizados
