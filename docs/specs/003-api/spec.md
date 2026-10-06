# Spec 003 — API

Fase 5 de [`docs/PLANO.md`](../../PLANO.md). Garantias e passos do avaliador cobertos: contrato da API (constituição 7, passos 2 a 14), G1 pela rota (409 antes do `Runner`: passos 7, 8, 9, 11), G2 na criação da sessão (passo 2), G3 (sessão e eventos sobrevivem ao reinício: passo 13), rotas de verificação (passos 1, 3 a 13), `aurora-api` e `aurora-restore` como os dois comandos do README (passo 1).

## Escopo

1. `adapters/api/`: aplicação FastAPI com as seis rotas do contrato, por cima de `construir_runner`, `criar_sessao`/`buscar_sessao` e `pendentes`/`resposta_de_confirmacao`, que já existem desde a Fase 4.
2. `adapters/adk/conversa.py`: os dois movimentos de conversa (enviar texto, responder confirmação) que hoje vivem em `tests/support/conversa.py`, devolvendo o texto da resposta e as pendências. A API e os testes passam a usar o mesmo código.
3. Serialização dos eventos para `GET /sessoes/{id}/eventos`.
4. Comando `aurora-api` (sobe em `localhost:8000`, lê o `.env`).
5. Flag `--sessoes` no `aurora-restore`, adiada desde a Fase 3.
6. Testes da API com `httpx.AsyncClient` + `ASGITransport` e `ScriptedLlm`, sem `GOOGLE_API_KEY`.

Fora desta spec: disputa concorrente pela API (passo 14) e revisão adversarial das garantias (Fase 6); script E2E do avaliador e README (Fase 7).

## Garantias nesta fase

| Garantia | Onde fica, nesta fase |
|---|---|
| G1 Confirmação | A rota de confirmações confere se o `id` está em `pendentes(sessao.events)` **antes** de chamar o `Runner`. Fora da lista → `409`, nada executa. Sem a guarda, id inexistente vira `ValueError` no `Runner` (500) e id já respondido é aceito em silêncio (`DESAFIOS.md`) |
| G2 Sessão = apartamento | `POST /sessoes` é o único ponto em que o apartamento entra, e só vai para o `state`. Nenhuma outra rota aceita apartamento no corpo. As rotas de verificação recebem o apartamento no caminho, mas não passam pelo modelo |
| G3 Reinício | Nada em memória: sessões e eventos no `SqliteSessionService`, pendências derivadas dos eventos. Um app novo sobre o mesmo banco devolve os mesmos eventos e retoma a confirmação |
| G4 Regulamento | Nada novo: a rota só repassa a mensagem. O teste da API confere que `GET /eventos` não tem evento autorado por `regulamento` |
| G5 Concorrência | Nada novo nesta fase: `data_indisponivel` já é resultado da tool, então a aprovação perdedora responde `200`. Teste concorrente pela API fica na Fase 6 |

## Contrato

Exatamente o do enunciado (`docs/enunciado-original.md`, "Contrato da API"). Toda rota com `{session_id}` responde `404` quando a sessão não existe, e essa checagem vem antes de qualquer outra.

| Rota | Corpo | Sucesso | Erros |
|---|---|---|---|
| `POST /sessoes` | `{"apartamento": "101"}` | `201 {"session_id"}` | `422` apartamento inexistente |
| `POST /sessoes/{id}/mensagens` | `{"texto"}` | `200 {"resposta", "confirmacoes_pendentes"}` | `404`, `503` modelo indisponível |
| `POST /sessoes/{id}/confirmacoes` | `{"id", "confirmado"}` | `200`, mesmo formato da anterior | `404`, `409`, `503` |
| `GET /sessoes/{id}/eventos` | — | `200 [evento, ...]` | `404` |
| `GET /apartamentos/{n}/reservas` | — | `200 [{"codigo", "area", "data"}]` | — |
| `GET /apartamentos/{n}/visitantes` | — | `200 [{"nome", "data"}]` | — |

`confirmacoes_pendentes` é `[{"id", "acao", "detalhes"}]`, lido de `PendenciaConfirmacao` (o campo `tool` não sai na API).

## Decisões de design desta fase

- **`resposta` é o texto das respostas finais desta chamada.** Junta, em ordem, o texto dos eventos da execução corrente em que `event.is_final_response()` é verdadeiro e o autor não é `user`, sem as partes `thought`. Quando a execução para no pedido de confirmação, não há resposta final em texto e `resposta` sai `""`, como o contrato permite. Só a execução corrente: a resposta do turno anterior não volta.
- **`confirmacoes_pendentes` é relida da sessão depois da execução**, e não coletada dos eventos que passaram pelo `async for`. O contrato pede "todas as pendências da sessão no momento da resposta", o que inclui pedidos de mensagens anteriores ainda abertos. Uma leitura a mais do banco por requisição; em troca, a mesma função (`pendentes`) serve à resposta e à guarda do 409.
- **A guarda do 409 lê a sessão, não um cache.** Pendência é derivada dos eventos persistidos, então vale depois do reinício e entre processos. Não há estado paralelo para dessincronizar.
- **Apartamento inexistente na criação da sessão → `422`.** O enunciado deixa livre, mas aceitar abre um 500 real: a primeira reserva da sessão bate na FK de `apartamentos` e sobe como `IntegrityError`, que não é erro de domínio (`DESAFIOS.md`). Validar na porta de entrada fecha isso num lugar só. `422` e não `404`, porque o recurso do caminho (`/sessoes`) existe; o que está errado é o corpo. Exige uma porta de leitura de apartamento (`ApartamentoRepository.existe`).
- **Rotas de verificação para apartamento inexistente → `200 []`.** Também é livre no enunciado; lista vazia é verdade (não há reservas) e não pede código novo.
- **Rotas de verificação pelos serviços, não pelo modelo.** `ReservasService.minhas_reservas` e `VisitantesService.meus_visitantes`, que leem o SQLite direto. Reserva só ativa (cancelada não aparece, passo 5). Ordem por data.
- **Eventos serializados como o próprio ADK faz.** `event.model_dump(mode="json", by_alias=True, exclude_none=True)`, a forma do `api_server` do ADK (`adk web`). Conteúdo completo, na ordem da sessão, sem filtro: é ali que o avaliador procura vazamento (passos 3, 4, 10, 12), então esconder algo na serialização mascararia defeito em vez de corrigir.
- **Fábrica de app recebe o runner pronto.** `criar_api(runner, reservas, visitantes, apartamentos)` monta as rotas; `aurora-api` monta o runner do ambiente (`construir_runner`) e os serviços sobre o mesmo `SqliteRepository`. Nos testes, o runner vem da `FabricaDeRunner` com `ScriptedLlm`. Sem variável global e sem `Depends` sobre singleton de módulo.
- **"Reiniciar" nos testes é criar um app novo sobre o mesmo arquivo.** Mesmo critério da Fase 4 (Runner novo = processo novo): só o SQLite atravessa.
- **`aurora-api` lê o `.env`.** O ADK como biblioteca não lê `.env`, e o avaliador só copia `.env.example` para `.env` e roda o comando do README (passo 1). `load_dotenv(override=False)` antes de montar o runner: variável já exportada no shell continua valendo. `python-dotenv` já está no `uv.lock` por dependência do ADK; vira dependência direta, porque o código passa a importá-la.
- **Host e porta.** `127.0.0.1:8000` por padrão, `AURORA_HOST`/`AURORA_PORT` para trocar. `uvicorn.run` sem `reload`: Ctrl+C encerra, e subir de novo com o mesmo comando é o passo 13.
- **Schema garantido na subida.** O `lifespan` chama `create_schema` (idempotente, `IF NOT EXISTS`), para a API não quebrar se subir antes do restore. Dados iniciais continuam só no `aurora-restore`: subir a API não pode desfazer o que a conversa gravou (passo 13).
- **Modelo indisponível → `503`.** `google.genai.errors.ServerError` (503 "high demand") e `ClientError` 429 viram `503` com `{"detail": ...}` dizendo para trocar `AURORA_MODELO_*`. Sem isso o avaliador vê um 500 sem pista. O evento do usuário pode já estar gravado; a sessão continua utilizável na próxima mensagem. Qualquer outra exceção continua 500: defeito não vira mensagem bonita.
- **`aurora-restore --sessoes`** apaga as tabelas do `SqliteSessionService` (`events`, `sessions`, `user_states`, `app_states`) no mesmo banco. Sem a flag, sessões ficam: restaurar dados não deve, por padrão, apagar conversas. O enunciado deixa a escolha livre; a flag dá as duas.
- **Modelos Pydantic da API em `adapters/api/schemas.py`**, com os nomes de campo do contrato. Corpo inválido (`texto` ausente, `confirmado` não booleano) fica com o `422` padrão do FastAPI.
- **Uma mensagem por vez por sessão não é garantida.** Duas requisições simultâneas na mesma sessão são fora de escopo no enunciado ("nova mensagem com confirmação pendente: livre", "duas respostas simultâneas para a mesma confirmação: livre"). Nenhuma trava por sessão nesta fase.

## Critérios de aceite

- `POST /sessoes` com apartamento existente responde `201` e um `session_id` utilizável; com apartamento inexistente, `422` (passo 2).
- `GET /sessoes/sessao-inexistente/eventos` responde `404`, e o mesmo vale para `mensagens` e `confirmacoes` (passo 9).
- Mensagem que reserva área sem taxa: `200`, `confirmacoes_pendentes == []` e a reserva aparece em `GET /apartamentos/101/reservas` (passo 6).
- Mensagem que reserva área com taxa: `200`, uma pendência com `area` e `data` em `detalhes`, nada em `GET /apartamentos/101/reservas`; `confirmado: false` responde `200` e continua sem reserva (passo 7).
- Aprovar grava exatamente uma reserva; reenviar o mesmo `id` responde `409` e não grava de novo (passo 8).
- `id` inexistente responde `409` e não altera reservas (passo 9).
- Autorizar visitante gera pendência com `nome` e `data`; aprovar faz o visitante aparecer em `GET /apartamentos/101/visitantes` (passo 11).
- `GET /eventos` devolve todos os eventos em ordem, com function calls e responses completos, e nenhum autorado por `regulamento` (passo 12).
- Um app novo sobre o mesmo banco devolve a mesma quantidade de eventos, aceita mensagem nova (que aumenta a contagem) e aprova uma pendência aberta antes do "reinício" (passo 13).
- `GET /apartamentos/101/reservas` e `GET /apartamentos/302/visitantes` devolvem os dados iniciais no formato do contrato após `aurora-restore` (passo 1).
- `aurora-restore --sessoes` apaga as sessões; sem a flag, elas ficam.
- `ServerError` do modelo vira `503`, não `500`.
- `ruff`, `mypy` strict e `pytest` verdes sem `GOOGLE_API_KEY`.
