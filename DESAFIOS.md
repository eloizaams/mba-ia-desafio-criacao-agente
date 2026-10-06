# Desafios e pontos de fricção

Pontos que custaram tempo e podem reaparecer. Ler ao iniciar uma sessão nova.

> Fricções de git (refs defasados, PR mergeado sem o último commit) não ficam aqui:
> são do fluxo do usuário, não do projeto. Estão na skill `abrir-pr`.

## ADK 2.11.0

### `DatabaseSessionService` não funciona sem o extra `[db]`
Ele importa SQLAlchemy, que não é dependência base do `google-adk`. O acesso é
lazy em `sessions/__init__.py` e falha com "missing extra".
**Saída:** usar `SqliteSessionService(db_path=...)`, que fala `aiosqlite` direto.
Ver `docs/ADK-CONFIRMACAO.md`.

### Sub-agente travado quebra a retomada de confirmação, em silêncio
Com `disallow_transfer_to_parent=True` + `disallow_transfer_to_peers=True` no
sub-agente, aprovar uma confirmação **não executa a tool** e **não levanta erro**:
nenhum agente roda. Não deixar os especialistas de Aurora travados assim.

### `AgentTool` é "discouraged" pela documentação, mas é o certo aqui
O docstring sugere `mode='single_turn'` + `sub_agents`, que roda o sub-agente
*inline na sessão do pai* — o oposto do isolamento que a Garantia 4 pede.
Justificar a escolha no README para que não pareça desatualização.

### `hint` da confirmação não está onde parece
No call `adk_request_confirmation`, a dica está em
`args["toolConfirmation"]["hint"]`, não em `args["hint"]`.

### Features experimentais com `UserWarning`
`ResumabilityConfig` e `TOOL_CONFIRMATION` avisam que podem mudar sem aviso.
É a razão de a versão do ADK estar fixada em `==2.11.0`. Ao subir a versão,
rerodar o spike antes de qualquer outra coisa.

### Modelos: os exemplos do ADK apontam para modelos legados
O código do ADK 2.11 cita `gemini-2.5-flash` 32 vezes, mas a série 2.5 está
**legada**, com acesso restrito a projetos existentes. Conferir sempre em
`ai.google.dev/gemini-api/docs/models` em vez de copiar dos exemplos.

## SQLite

### Índice único parcial não aparece pelo nome na mensagem de erro
Com `CREATE UNIQUE INDEX ... WHERE status='ativa'`, a violação vira
`UNIQUE constraint failed: reservas.area, reservas.data`. O nome do índice
(`uq_reserva_ativa_area_data`) não aparece. Já `UNIQUE(codigo)` aparece como
`reservas.codigo`. Para distinguir os dois, o adaptador checa as colunas.
Testes de integração (`tests/integration/test_repositorio_reservas.py`) cobrem os dois casos.

### `IntegrityError` não separa as constraints
`IntegrityError` cobre `UNIQUE`, `FOREIGN KEY` e `CHECK`. Para tratar só a
agenda como "data indisponível", é preciso olhar a mensagem. Uma FK inválida
(área ou apartamento inexistente) ainda sobe como `IntegrityError`, então a
camada de aplicação precisa validar a existência antes de gravar.

## Testes com LLM

### Testar agentes sem chave de API
Uma subclasse de `BaseLlm` que decide o turno **a partir do histórico**
(`llm_request.contents`), não de um contador interno, permite testar confirmação,
retomada e persistência de forma determinística e sobrevive ao reinício do
processo. Ver `spike/scripted_llm.py`.

**Armadilha:** um modelo roteirizado sem porta de saída reemite a mesma chamada
para sempre e estoura `LlmCallsLimitExceededError: Max number of llm calls limit
of 500`. Toda regra que emite um function call precisa de uma condição
correspondente que detecte a resposta daquela tool e feche o turno em texto.

### Uma instância de modelo roteirizado por agente
Com uma instância compartilhada, o sub-agente também enxergava
`transfer_to_agent` e tentava transferir para si mesmo
(`WorkflowDataError: Agent 'reservas' cannot transfer to itself`). O papel
(roteador × especialista) tem de ser um campo do modelo.

## Ferramental

### `ruff check --fix` não quebra linha longa; `ruff format` nem sempre
`E501` em f-string de uma linha não é corrigido por nenhum dos dois. Extrair a
expressão para uma variável antes. Ordem certa: `ruff format` **depois**
`ruff check --fix`.

## Ambiente de testes com Gemini

### Chave válida, mas sem crédito: `402 RESOURCE_EXHAUSTED`
A chave autentica e a requisição chega ao modelo, mas o projeto do AI Studio
está sem crédito pré-pago. A resposta é `402 ... Your prepayment credits are
depleted`. O erro aparece na primeira chamada ao modelo, então o spike falha
no meio do `abrir` e pode deixar uma sessão pela metade no banco.
**Saída:** conferir o crédito em `ai.studio/projects` antes de rodar os testes
reais. Para descartar a sessão pela metade, apague `spike/spike_sessoes.db`.

### `503 UNAVAILABLE` ("high demand") no modelo do topo da lista
Depois de liberar crédito, `gemini-3.8-flash` respondeu `503 UNAVAILABLE` em
todas as tentativas de uma janela de vários minutos. A mesma topologia rodou
inteira com `gemini-3.5-flash` (T3 a T6). Erro transitório do lado do Google,
não do código. Ao rodar testes reais, valer-se de um segundo modelo estável
como reserva, parametrizado por `AURORA_MODELO_*`, sem editar o código.
