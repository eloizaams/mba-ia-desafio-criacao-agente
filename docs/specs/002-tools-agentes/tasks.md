# Tarefas 002 — Tools e agentes

- [x] `domain/datas.py`, `AreaDesconhecida`, `domain/regulamento.py` (capítulos e relevância) + teste unitário
- [x] Portas: `AreaRepository.listar()`, `RegulamentoRepository`; `listar()` no `SqliteRepository`
- [x] `ServicoReservas` (listar, disponibilidade, reservar, cancelar por área e data, gera_cobranca)
- [x] `ServicoVisitantes` (listar, autorizar)
- [x] `RegulamentoArquivo` + `ServicoRegulamento`
- [x] Testes de integração dos serviços sobre o SQLite real
- [x] `adapters/adk/estado.py`: apartamento da sessão
- [x] Tools de reservas, visitantes e regulamento (fábricas que recebem o serviço)
- [x] `require_confirmation`: callable (taxa > 0) em `reservar`, `True` em `autorizar_visitante`
- [x] `agentes.py`: `aurora` (root) + `reservas`/`visitantes` como `sub_agents` + `regulamento` como `AgentTool`
- [x] `app.py`: `App` com `ResumabilityConfig(is_resumable=True)` e `construir_runner` com `SqliteSessionService`
- [x] `sessoes.py`: apartamento no `state` na criação, `user_id` fixo (a sessão é achada só pelo `session_id`)
- [x] `confirmacoes.py`: pendências derivadas dos eventos + mensagem de resposta
- [x] `ScriptedLlm` por papel em `tests/support/`, com o roteiro declarado pelo teste
- [x] Testes pelo `Runner`: taxa zero sem pendência, taxa com pendência, aprovar grava uma vez, negar não grava
- [x] Teste pelo `Runner`: aprovação num `Runner` novo (API reiniciada) grava uma vez só
- [x] Testes pelo `Runner`: cancelar sem pendência, visitante com pendência, data ocupada sem vazar dono
- [x] Testes pelo `Runner`: sessão do 101 não traz `RSV-4821`, `Marina Duarte` nem "302 isolado" aos eventos
- [x] Teste: a sessão do pai não tem evento autorado por `regulamento`, nem trecho de outro capítulo (G4)
- [x] Teste estrutural: nenhuma tool aceita apartamento e só cobrança/acesso confirmam (passo 15)
- [x] `ruff check`, `ruff format --check`, `mypy`, `pytest` verdes (80 testes, sem chave de API)

Descobertas que foram para `DESAFIOS.md`: assinatura do callable de
`require_confirmation`, `hint` fixo em inglês, `ValueError` do `Runner` com id de
confirmação inexistente (por que a guarda do 409 vem antes do `Runner`), reenvio do
mesmo id não reexecuta a tool, aviso de `context_cache_config`, `__init__.py` em
`tests/`.

Adiado para a Fase 5, de propósito: rotas HTTP, serialização dos eventos, 404/409,
e o `--sessoes` do `aurora-restore`.
