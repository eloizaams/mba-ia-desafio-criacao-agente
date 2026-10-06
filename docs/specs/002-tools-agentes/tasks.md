# Tarefas 002 — Tools e agentes

- [x] `domain/datas.py`, `AreaDesconhecida`, `domain/regulamento.py` (capítulos e relevância) + teste unitário
- [x] Portas: `AreaRepository.listar()`, `RegulamentoRepository`; `listar()` no `SqliteRepository`
- [x] `ReservasService` (listar, disponibilidade, reservar, cancelar por área e data, gera_cobranca)
- [x] `VisitantesService` (listar, autorizar)
- [x] `RegulamentoArquivo` + `RegulamentoService`
- [x] Testes de integração dos serviços sobre o SQLite real
- [x] `adapters/adk/state.py`: apartamento da sessão
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
- [x] Testes pelo `Runner`: sessão do 101 não traz `RSV-4821` nem `Marina Duarte` aos eventos (passos 3 e 4)
- [x] Teste pelo `Runner`: "302 isolado" fora dos eventos nos passos 4 e 10 — no passo 3 não vale, porque é o próprio morador que escreve "302" na mensagem
- [x] Teste: a sessão do pai não tem evento autorado por `regulamento`, nem trecho de outro capítulo (G4)
- [x] Teste estrutural: nenhuma tool aceita apartamento e só cobrança/acesso confirmam (passo 15)
- [x] `ruff check`, `ruff format --check`, `mypy`, `pytest` verdes (91 testes, sem chave de API)

Descobertas que foram para `DESAFIOS.md`: assinatura do callable de
`require_confirmation`, `hint` fixo em inglês, `ValueError` do `Runner` com id de
confirmação inexistente (por que a guarda do 409 vem antes do `Runner`), reenvio do
mesmo id não reexecuta a tool, aviso de `context_cache_config`, `__init__.py` em
`tests/`.

Adiado para a Fase 5, de propósito: rotas HTTP, serialização dos eventos, 404/409,
e o `--sessoes` do `aurora-restore`.

## Smoke test com Gemini real (2026-10-06)

- [x] Fluxo do avaliador (passos 3, 4, 5, 6, 7, 8, 11, 12) numa sessão só, com `gemini-3.5-flash-lite`
- [x] Correção de instrução: confirmação negada não se refaz (o modelo chamava `reservar` de novo)
- [x] Correção de instrução: resultado da tool é do apartamento da sessão e não pode ser apresentado como de outro
- [x] 70 eventos, sem `RSV-4821`, sem `Marina Duarte`, sem evento autorado por `regulamento`

## Depois do `code-review` (eixos Standards e Spec)

- [x] Convenção PT/EN: `ServicoX` → `XService`, `portas.py` → `ports.py`, `estado.py` → `state.py`, `resultados.py` → `results.py` (constituição, Convenções)
- [x] `ReservaFeita`: `reservar` devolve a reserva e se gera cobrança, com uma leitura só da área
- [x] `traduz_erro_de_dominio`: o `try/except` repetido vira decorator (declaração do ADK conferida por teste)
- [x] `REGRAS_COMUNS`: as duas regras repetidas nas três instruções ficam num lugar só
- [x] `modelos_do_ambiente` → `modelo_do_ambiente` (devolve um modelo, não vários)
- [x] `PendenciaConfirmacao.autor` removido: era escrito e nunca lido
- [x] `area_desconhecida` documentado na spec e ensinado na instrução do especialista
- [x] Teste do passo 15 caminha pela topologia real, e cobre também o conjunto de tools esperado
- [x] `tests/unit/test_resultados_de_tool.py`: mapa de status, erro não-domínio que continua subindo, assinatura preservada
- [x] Teste: área inexistente não pede confirmação nem grava (decisão deliberada, agora especificada)
- [x] Teste: `nao_encontrada` no cancelamento de reserva alheia (passo 4)
- [x] Teste pelo `Runner`: segunda consulta ao regulamento por título, provada por asserção que cai sem ela
- [x] `tests/support/condominio.py`: constantes do seed e `FabricaDeRunner` num lugar só
- [x] `plan.md` atualizado com `sessoes.py`, `results.py` e os nomes novos
