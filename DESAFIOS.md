# Desafios e pontos de fricção

Pontos que custaram tempo e podem reaparecer. Ler ao iniciar uma sessão nova.

## Git

### Refs locais defasados depois de merge pelo GitHub
**Sintoma:** `git log`/`git rev-parse` mostram `develop` e `main` atrasados e eu
concluí que a Fase 1 não tinha sido mergeada — ela tinha, via PRs #1 e #2 na
interface do GitHub.
**Correção:** `git fetch --all --prune` **antes** de qualquer leitura de estado de
branch. O `gitStatus` que vem no início da sessão é um retrato do disco, não do
remoto.

### PR aberto antes do último commit da branch
**Sintoma:** o PR #1 (`feature/setup` → `develop`) foi mergeado sem o commit
`ef0a894` (`docs/enunciado-original.md`), que entrou depois. Resultado: `main`
ficou à frente de `develop`.
**Correção:** back-merge `main` → `develop` para reconvergir. Evitar: empurrar
commits novos para a branch **antes** de mergear o PR, ou conferir
`git log origin/<branch>..HEAD` antes de mergear.

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
