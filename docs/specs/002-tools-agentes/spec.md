# Spec 002 — Tools e agentes

Fase 4 de [`docs/PLANO.md`](../../PLANO.md). Garantias e passos do avaliador cobertos: G1 (confirmação: passos 6, 7, 8, 11), G2 (sessão = apartamento: passos 3, 4, 5, 10), G4 (regulamento isolado: passo 12), passo 15 (tools gravam e leem; nenhuma tool aceita apartamento do modelo; agente principal sem o regulamento).

## Escopo

1. Casos de uso em `application/`: `ReservasService`, `VisitantesService`, `RegulamentoService` (portas em `application/ports.py`). É aqui que a validação de existência (área) e de formato (data) acontece, antes de qualquer gravação.
2. Divisão do regulamento em capítulos e seleção do capítulo pertinente, como regra de domínio (`domain/regulamento.py`), com adaptador de leitura do arquivo em `adapters/regulamento.py`.
3. Tools ADK em `adapters/adk/`, finas: leem o apartamento da sessão, chamam um caso de uso, traduzem o resultado (ou o erro de domínio) em `dict` para o modelo.
4. Topologia: agente principal `aurora` com `reservas` e `visitantes` como `sub_agents` e `regulamento` como `AgentTool`.
5. Criação e leitura de sessão (`adapters/adk/sessoes.py`, onde o apartamento entra no `state`), derivação das confirmações pendentes a partir dos eventos e a mensagem que responde uma confirmação. É código de ADK, não de HTTP: as rotas da Fase 5 só embrulham.
6. Testes com `ScriptedLlm` (sem `GOOGLE_API_KEY`), rodando o `Runner` de verdade com sessão em SQLite.

Fora desta spec: rotas HTTP, serialização de eventos para JSON, 404/409 (Fase 5); revisão adversarial das garantias (Fase 6).

## Garantias nesta fase

| Garantia | Onde fica, nesta fase |
|---|---|
| G1 Confirmação | `require_confirmation` nas tools de escrita: callable (`taxa > 0`) em `reservar`, `True` em `autorizar_visitante`. O pedido é do ADK; a tool não roda antes da resposta |
| G2 Sessão = apartamento | `adapters/adk/state.py`: o apartamento vem de `tool_context.state`. Nenhuma tool tem parâmetro de apartamento, e isso é um teste (`test_nenhuma_tool_aceita_apartamento`) |
| G4 Regulamento | `regulamento` é `AgentTool` (sessão própria) e `consultar_regulamento` devolve só o capítulo pertinente. O agente principal não recebe o regulamento |
| G5 Concorrência | já é da Fase 3 (constraint). Aqui só não se atrapalha: `DataIndisponivel` virar resultado normal da tool, nunca exceção |

## As tools

Todas sem parâmetro de apartamento. `tool_context.state["apartamento"]` é a única fonte.

**Especialista `reservas`**

| Tool | Argumentos | Devolve | Confirmação |
|---|---|---|---|
| `listar_areas` | — | id, nome, taxa, `gera_cobranca` de cada área | não |
| `listar_minhas_reservas` | — | código, área, data das reservas ativas do apartamento da sessão | não |
| `verificar_disponibilidade` | `area`, `data` | `"livre"` ou `"ocupada"`, mais o eco da área e da data perguntadas. Nada sobre quem reservou (constituição 5) | não |
| `reservar` | `area`, `data` | código, área, data e se gera cobrança | **se `taxa > 0`** |
| `cancelar_minha_reserva` | `area`, `data` | código cancelado, ou "não encontrada" | não (regra de negócio 4) |

**Especialista `visitantes`**

| Tool | Argumentos | Devolve | Confirmação |
|---|---|---|---|
| `listar_meus_visitantes` | — | nome e data dos visitantes do apartamento da sessão | não |
| `autorizar_visitante` | `nome`, `data` | nome e data autorizados | **sempre** |

**Agente `regulamento`** (acionado como `AgentTool`)

| Tool | Argumentos | Devolve | Confirmação |
|---|---|---|---|
| `consultar_regulamento` | `topico` | o(s) capítulo(s) pertinente(s); se nada casar, só os títulos, para uma segunda tentativa | não |

## Decisões de design desta fase

- **Cancelar por área e data, não por código.** O avaliador escreve "cancele a minha reserva da quadra do dia 2030-03-09" (passo 5). Com `(area, data)` o modelo não precisa manipular código nenhum: o caso de uso resolve o código dentro das reservas *do apartamento da sessão*. A reserva do 302 simplesmente não está nessa lista, então o passo 4 devolve "não encontrada" sem que `RSV-4821` chegue perto da conversa. O par `(área, data)` identifica uma reserva ativa sem ambiguidade, porque o índice único garante isso.
- **`listar_areas` é tool, não texto na instrução.** O modelo precisa mapear "salão de festas" para `salao-de-festas`. Colocar a lista na instrução congelaria dado de banco em prompt; uma tool mantém a regra "reservas são lidas por tools" (requisito 1) e sobrevive a mudança de área. Custa uma chamada a mais ao modelo.
- **Confirmação pela via nativa do ADK.** `require_confirmation` recebe um callable com a *mesma assinatura* da tool (o ADK invoca `callable(**args_da_tool)`), então `reservar` e seu callable compartilham `(area, data, tool_context)` e o callable pergunta ao caso de uso se a área gera cobrança — o mesmo método que depois preenche `cobranca` no resultado. O `hint` do ADK é um texto genérico em inglês, não configurável por essa via; o texto em português de `acao` é montado na derivação das pendências, a partir do nome da tool, e não no `hint`.
- **`detalhes` da pendência são os argumentos originais da tool.** Como nenhuma tool recebe apartamento, os argumentos são exatamente o que o enunciado pede em `detalhes` (`{"area", "data"}` ou `{"nome", "data"}`). Não há filtro a aplicar, e por construção nada de outro apartamento aparece ali.
- **Seleção de capítulo por termos, com o título pesando mais.** O peso do título (10) acima do corpo (1 por termo distinto) evita que uma palavra comum como "domingos", que aparece em vários capítulos, arraste a resposta para o capítulo errado. Devolve o melhor capítulo e, só em quase-empate (≥ 60% do melhor), um segundo — para pergunta que legitimamente cruza dois capítulos ("piscina e churrasqueira"). Nunca mais de dois.
- **Tools síncronas.** O ADK 2.11.0 invoca tool síncrona dentro do loop de eventos (`_SYNC_CALLABLE_RUNNER` fica vazio). O efeito é serializar as gravações dentro do processo, o que não atrapalha a Garantia 5: a exclusividade é da constraint, e o `busy_timeout` cuida de escritas de outros processos ou threads. Manter síncrono evita embrulhar o repositório inteiro em `asyncio.to_thread` sem necessidade.
- **Erro de domínio é resultado, não exceção.** Toda tool devolve `{"status": ..., "motivo": ...}`, pelo decorator `traduz_erro_de_dominio`. `DataIndisponivel` → `data_indisponivel`; `ReservaNaoEncontrada` → `nao_encontrada`; `AreaDesconhecida` → `area_desconhecida`; `DadoInvalido` → `invalido`; erro de domínio novo cai em `invalido`. Cada status tem uma linha na instrução do especialista, para o modelo saber o que dizer. Nenhuma exceção de domínio sobe para o `Runner`, e erro que **não** é de domínio continua subindo: defeito de programação não vira resultado para o modelo.
- **A porta da confirmação responde "não cobra" para área inexistente.** `gera_cobranca` devolve `False` quando a área não existe, então um pedido com área inventada não gera pendência. É deliberado: `reservar` recusa com `area_desconhecida` antes de qualquer escrita, então não há ação a confirmar — confirmar um pedido impossível só confundiria o morador. Coberto por `test_area_inexistente_nao_pede_confirmacao_nem_grava`.
- **Nomes.** Classes de serviço e o módulo de portas em inglês (`ReservasService`, `ports.py`), como manda a constituição ("termos técnicos em inglês"); o que nomeia conceito do enunciado continua em português (`reservas`, `visitantes`, `confirmacoes`, `sessoes`). Vale para módulo também: `ports.py`, `state.py` e `results.py` são termos técnicos.
- **Uma instância de `ScriptedLlm` por agente nos testes.** Compartilhar a instância fez o especialista tentar transferir para si mesmo na Fase 2 (`DESAFIOS.md`). O papel é campo do modelo.

## Critérios de aceite

- Reservar área com taxa gera pendência com `area` e `data` em `detalhes` e **não grava**; aprovar grava uma vez; negar não grava (passos 7 e 8).
- Reservar área com taxa zero não gera pendência e grava (passo 6).
- Autorizar visitante gera pendência com `nome` e `data`, mesmo com "já estou confirmando aqui" na mensagem (passo 11).
- Cancelar reserva própria não gera pendência (passo 5).
- Numa sessão do 101, pedir dados ou cancelamento do 302 não altera nada e não leva `RSV-4821` nem `Marina Duarte` para os eventos (passos 3 e 4).
- Reservar data já ocupada devolve `data_indisponivel`, sem dizer de quem é a reserva (passo 10).
- A sessão do pai não contém nenhum evento autorado por `regulamento`, e a resposta sobre a piscina aos domingos traz o horário de fechamento (passo 12).
- Nenhuma função de tool tem parâmetro de apartamento (passo 15), verificado por um teste que caminha pela topologia de verdade (root, `sub_agents` e o agente dentro do `AgentTool`), não por uma lista remontada à mão.
- Tópico sem capítulo devolve os títulos e o agente acerta na segunda consulta, sem nunca receber o documento inteiro.
- `ruff`, `mypy` strict e `pytest` verdes sem `GOOGLE_API_KEY`.
