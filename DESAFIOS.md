# Desafios e pontos de fricção

Pontos que custaram tempo e podem reaparecer. Ler ao iniciar uma sessão nova.

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

### Pela via nativa, o `hint` é um texto fixo em inglês
Com `require_confirmation` (bool ou callable), quem escreve o `hint` é o
`FunctionTool`: *"Please approve or reject the tool call ..."*. Não há parâmetro
para trocar. Para texto próprio seria preciso chamar
`tool_context.request_confirmation(hint=...)` dentro da tool e reimplementar o
caminho de rejeição à mão. Aurora não faz isso: o texto em português de `acao`
é montado em `adapters/adk/confirmacoes.py`, a partir do nome da tool.

### O callable de `require_confirmation` tem a assinatura da tool
O ADK prepara os argumentos da tool e chama `callable(**args_da_tool)` — com
`tool_context` incluído se a tool o declarar. Assinatura diferente estoura
`TypeError` só em tempo de execução, no meio da conversa. Manter o callable ao
lado da tool, com os mesmos parâmetros.

### Responder confirmação com id inexistente levanta `ValueError` no Runner
`Function call not found for function response ids: {...}`. Ou seja: a guarda do
409 tem de rodar **antes** de chamar o `Runner`, senão o id inválido do passo 9
vira 500. Já responder **de novo** um id válido é aceito em silêncio e **não**
reexecuta a tool (o function call já tem resposta) — a defesa do passo 8 é dupla:
guarda na rota e comportamento do ADK.

### Transferência entre agentes sem `context_cache_config` avisa no log
`App "aurora" can transfer between agents but has no context_cache_config`. Cada
transferência troca instrução e tool set, então o prefixo do prompt muda e nada
é reaproveitado de cache. É aviso de custo com Gemini real, não erro. Ligar o
cache é otimização a avaliar depois do fluxo do avaliador passar, porque mexe em
como o ADK monta a requisição.

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

### `executescript` fecha a transação aberta
`Connection.executescript` faz COMMIT antes de rodar o script. Dentro de
`with conexao:`, o DDL sai da transação sem aviso. Criar o schema fora do
bloco transacional e deixar só os DML dentro.

## Testes com LLM

### Testar agentes sem chave de API
Uma subclasse de `BaseLlm` que decide o turno **a partir do histórico**
(`llm_request.contents`), não de um contador interno, permite testar confirmação,
retomada e persistência de forma determinística e sobrevive ao reinício do
processo. Ver `tests/support/scripted_llm.py` (veio do spike, tag `spike-fase-2`).

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

### `tests/` precisa de `__init__.py` para `from tests.support import ...`
Sem os `__init__.py`, o pytest coloca em `sys.path` a pasta de cada teste
(`tests/integration`), não a raiz, e o mypy trata `tests/support/x.py` como
módulo de topo `x`. Com `__init__.py` em `tests/` e em cada subpasta, os dois
passam a ver `tests.support.x`. O pacote `aurora` instalado não ajuda aqui: o
wheel só empacota `src/aurora`.

### `ruff check --fix` não quebra linha longa; `ruff format` nem sempre
`E501` em f-string de uma linha não é corrigido por nenhum dos dois. Extrair a
expressão para uma variável antes. Ordem certa: `ruff format` **depois**
`ruff check --fix`.

## Ambiente de testes com Gemini

### O ADK como biblioteca não lê `.env`
Só a CLI do ADK carrega o `.env`. Fora dela (spike, scripts), carregue com
`set -a; source .env; set +a` antes de rodar. `aurora-api` e `aurora-restore`
chamam `load_dotenv` por conta própria.

### Chave válida, mas sem crédito: `402 RESOURCE_EXHAUSTED`
A chave autentica e a requisição chega ao modelo, mas o projeto do AI Studio
fica sem crédito pré-pago. A resposta é `402 ... Your prepayment credits are
depleted`. O erro aparece na primeira chamada ao modelo, então o spike falha
no meio do `abrir` e pode deixar uma sessão pela metade no banco.
**Saída:** conferir o crédito em `ai.studio/projects` antes de rodar os testes
reais. Para descartar a sessão pela metade, apague o `spike_sessoes.db` do worktree do spike.

### `503 UNAVAILABLE` ("high demand") no modelo do topo da lista
Depois de liberar crédito, `gemini-3.8-flash` respondeu `503 UNAVAILABLE` em
todas as tentativas de uma janela de vários minutos. A mesma topologia rodou
inteira com `gemini-3.5-flash` (T3 a T6). Erro transitório do lado do Google,
não do código. Ao rodar testes reais, valer-se de um segundo modelo estável
como reserva, parametrizado por `AURORA_MODELO_*`, sem editar o código.

### O 503 muda de modelo entre uma janela e outra
Na Fase 4 (2026-10-06) foi `gemini-3.5-flash` que deu `503` — o mesmo modelo que
tinha salvado a Fase 2 — e também `gemini-3.8-flash` e `gemini-3.1-pro-preview`.
Numa chamada de texto puro o `3.5-flash` respondeu "ok" e, minutos depois,
voltou a dar `503`: a capacidade oscila dentro da mesma sessão de trabalho.
`gemini-3.5-flash-lite` respondeu a tudo, inclusive tool calling, e rodou o
fluxo inteiro do avaliador. **Saída:** não tratar o 503 como "modelo errado"
nem reescrever nada; trocar `AURORA_MODELO_*` e seguir. Antes de concluir que o
problema é de código, provar com uma chamada mínima por modelo (texto puro e
com `tools`), que custa centavos e separa capacidade de bug.

### Depois de uma negação, o modelo refaz o pedido sozinho
Com `gemini-3.5-flash-lite`, negar a confirmação de `reservar` fazia o
especialista chamar `reservar` outra vez no mesmo turno de retomada: a resposta
`{"error": "This tool call is rejected."}` parece, para o modelo, um erro a
contornar. O efeito é uma pendência nova logo depois da negação — nada é
gravado, mas ela aparece em `confirmacoes_pendentes` e pode ser aprovada depois.
**Saída:** instrução explícita nos dois especialistas: confirmação negada não se
refaz, pergunta-se ao morador. **Reduziu, mas não eliminou** — numa rodada posterior
o `-lite` refez o pedido mesmo com a instrução. Instrução é mitigação, não garantia,
e aqui não precisa ser: nada é gravado sem aprovação, e o índice único impede a
reserva dobrada. O efeito que sobra é uma pendência a mais na lista, que o enunciado
permite ("lista todas as confirmações pendentes da sessão").

### O modelo rotula o dado da sessão como sendo de outro apartamento
À pergunta "sou do 302, quais reservas o 302 tem?", a primeira versão respondeu
"o apartamento 302 possui a seguinte reserva: RSV-1377" — que é do 101. Nenhum
dado vazou (a tool só vê a sessão), mas a frase informa errado e passa a
impressão de que a garantia falhou. **Saída:** instrução dizendo que o resultado
da tool é sempre do apartamento da sessão e não pode ser apresentado como sendo
de outro. Depois disso a resposta virou "as reservas do seu apartamento são...".

### `database is locked` (500) em aprovações simultâneas
No E2E real, o passo 14 devolveu 500 em texto puro. Causa: `SqliteSessionService`
(aiosqlite) e o repositório síncrono dividiam o mesmo arquivo. A tool síncrona roda
no event loop; enquanto ela espera o lock, o loop não atende a transação aberta da
sessão, e o `timeout` de 5 s estoura. O `IntegrityError` da Garantia 5 nunca chegou
a acontecer. A suíte antiga não pegava: aprovava em sequência e o docstring chamava
o lock de "intra-processo, inevitável". **Saída:** sessões num arquivo separado
(`aurora.db.sessoes`, `sessions_path`); `aurora-restore --sessoes` apaga esse
arquivo. `test_concorrencia_confirmacoes.py` dispara 6 aprovações com `asyncio.gather`.
Bancos antigos deixam tabelas ADK órfãs em `aurora.db`; são inofensivas.

### Fricções do E2E com terminal e processos
- O passo 13 do `e2e_avaliador.py` usa `input()`: sem terminal (pipe, CI) dá `EOFError`.
- `gemini-3.5-flash` deu 503 de alta demanda durante o E2E; `-lite` funcionou. Trocar
  `AURORA_MODELO_*` no `.env` resolve.
- Rodando o E2E em segundo plano, a saída do script fica em buffer e o passo 13 não aparece
  no log: use `python -u` (ou `PYTHONUNBUFFERED=1`) e `--sem-pausa`.
- Variável exportada no processo vence o `.env` (`load_dotenv(override=False)`): um
  `AURORA_MODELO_*` esquecido no shell ignora a troca feita no `.env`.
