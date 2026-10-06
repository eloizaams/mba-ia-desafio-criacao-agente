# Padrão comprovado: confirmação e retomada no ADK 2.11.0

Resultado da Fase 2 (branch `spike/adk-confirmacao`). Tudo aqui foi **executado**,
não lido na documentação. Reprodução:

```bash
cd spike
PYTHONPATH=. uv run python spike_confirmacao.py abrir            # processo 1
PYTHONPATH=. uv run python spike_confirmacao.py confirmar <id> --aprovar   # processo 2
PYTHONPATH=. uv run python spike_confirmacao.py confirmar <id> --negar
PYTHONPATH=. uv run python spike_confirmacao.py agent-tool
```

O spike roda **sem `GOOGLE_API_KEY`**: o modelo é um `ScriptedLlm` (subclasse de
`BaseLlm`) que emite function calls determinísticas a partir do histórico da
conversa. A mecânica testada é a do framework, não a do modelo — e por ser
reativa ao histórico, o roteiro continua correto depois de o processo reiniciar.

## O ciclo, em eventos

Um pedido de confirmação é um par de eventos na sessão:

```
[reservas] call reservar({area, data})              id=FC
[reservas] resp reservar -> {"error": "requires confirmation"}   id=FC
[reservas] call adk_request_confirmation({          id=CONF
             originalFunctionCall: {id: FC, name: "reservar", args: {...}},
             toolConfirmation: {hint: "...", confirmed: false}})
```

A retomada é um evento de autor `user` com um `FunctionResponse`:

```python
types.Content(
    role="user",
    parts=[
        types.Part(
            function_response=types.FunctionResponse(
                id=CONF,  # id do call adk_request_confirmation
                name="adk_request_confirmation",
                response={"confirmed": True},  # ou False
            )
        )
    ],
)
```

Entregue via `runner.run_async(user_id=..., session_id=..., new_message=...)`.
**Não é preciso informar `invocation_id`**: o `Runner` o deduz casando o id do
`FunctionResponse` contra os eventos da sessão (`_resolve_invocation_id`), que
vêm do banco. É isso que faz a retomada funcionar depois do reinício.

Depois da aprovação o ADK reexecuta a tool e grava a resposta real com o **mesmo
id `FC`**:

```
[user]     resp adk_request_confirmation -> {"confirmed": true}   id=CONF
[reservas] resp reservar -> {"status": "reservada", ...}          id=FC
```

Na negação, a tool **não roda**; a resposta gravada é
`{"error": "This tool call is rejected."}`.

## Resultados medidos

| # | Pergunta do plano | Resultado |
|---|---|---|
| 1 | `require_confirmation` dentro de um `sub_agent` gera o pedido? | **Sim.** Autor do pedido = `reservas` (o sub-agente), não o root. Tool não executa: contador em 0. |
| 2 | Retomada por `FunctionResponse` executa uma vez / nega sem executar? | **Sim.** Aprovar: 0 → 1 execução. Negar: 0 → 0. |
| 3 | Vale em **outro processo**? | **Sim.** Cada subcomando é um processo novo; só o SQLite atravessa. |
| 4 | O que faz a resposta voltar ao agente certo? | Ver "Roteamento", abaixo. |
| 5 | Eventos de `AgentTool` entram na sessão do pai? | **Não.** Autores na sessão do pai: `{user, aurora}`. `regulamento` não aparece. |
| 6 | Modelos Gemini | Ver "Modelos", abaixo. |

Confirmar duas vezes o mesmo pedido: a segunda vez não acha pendência — é a base
do **409** da rota `POST /sessoes/{id}/confirmacoes`.

## Roteamento da resposta (item 4)

`find_agent_to_run` (em `agents/_agent_router.py`) escolhe o agente por duas vias:

1. **Via explícita**: se o último evento é um function response, roteia para o
   autor do function call correspondente — mas **só quando
   `resumability_config.is_resumable=True`**.
2. **Via fallback**: varre os eventos de trás para frente e devolve o último
   agente que respondeu, se ele for transferível por toda a árvore
   (`is_transferable_across_agent_tree`).

Na topologia de Aurora (root → sub_agents com transferência livre) **as duas vias
levam ao mesmo lugar**, e o spike confirmou que a retomada funciona com
`is_resumable` em `True` *ou* `False`. Ainda assim: **usar `is_resumable=True`**,
porque a via 1 é explícita e não depende de o sub-agente poder transferir.

**Restrição descoberta:** com `disallow_transfer_to_parent=True` e
`disallow_transfer_to_peers=True` no sub-agente, a retomada **falha em silêncio**
— nenhum agente roda e a tool fica com 0 execuções, com `is_resumable` em `True`
ou `False`. Os sub-agentes de Aurora **não devem** ser travados assim.

Além disso, `_RequestConfirmationLlmRequestProcessor` só considera eventos do
**branch atual** e ignora pedidos autorados por outro agente. Reforça o mesmo
ponto: a confirmação é retomada pelo agente que a pediu.

## Isolamento do regulamento (item 5 → Garantia 4)

`AgentTool.run_async` cria um `Runner` próprio com **`InMemorySessionService` e
sessão nova**; os eventos do agente embrulhado não são repassados ao chamador —
só o conteúdo do último evento virа o resultado da tool. O state do pai é copiado
para dentro (menos chaves `_adk`) e o `state_delta` volta.

Ou seja, `AgentTool` entrega o isolamento da Garantia 4 **por construção**.

⚠️ O docstring do `AgentTool` em 2.11.0 diz que seu uso direto é "discouraged" e
sugere `mode='single_turn'` + `sub_agents`. Essa alternativa roda o sub-agente
**inline na sessão do pai** — exatamente o que a Garantia 4 proíbe. Então aqui
`AgentTool` é a escolha certa, e a justificativa é essa.

## Sessão persistida: `SqliteSessionService`, não `DatabaseSessionService`

`DatabaseSessionService` exige o extra `google-adk[db]` (SQLAlchemy) — **não
instalado** no projeto. O ADK traz `SqliteSessionService(db_path=...)`, que fala
`aiosqlite` direto (já é dependência) e é o que o **próprio CLI do ADK usa** para
armazenamento local (`cli/service_registry.py`, `cli/utils/local_storage.py`).

```python
from google.adk.sessions.sqlite_session_service import SqliteSessionService

servico = SqliteSessionService(db_path="aurora.db")
```

Não está em `sessions.__all__`, mas não é marcado como experimental nem
deprecado. Em troca, dispensa SQLAlchemy.

## Modelos (item 6)

Catálogo da Gemini API em outubro de 2026:

- `gemini-3.8-flash` — Flash estável (GA) mais recente, posicionado para
  "autonomous agents and complex enterprise workflows". Deu `503 UNAVAILABLE`
  (alta demanda) em todas as tentativas de uma janela de vários minutos.
- `gemini-3.5-flash` — Flash estável. Única opção que respondeu durante os
  testes reais; a topologia inteira (T3 a T6) passou nele.
- `gemini-3.5-flash-lite` — estável, mais barato.
- `gemini-3.1-pro-preview` — Pro **em preview**; não há Pro estável.
- A série 2.5 (`gemini-2.5-flash`, `gemini-2.5-pro`) é **legada**, com acesso
  restrito a projetos existentes. Não usar, apesar de ser o default em exemplos
  do ADK.

Escolha para Aurora: `gemini-3.5-flash` nos dois papéis (roteador e
especialistas) — estável, passou nos testes reais com tool calling e
confirmação. `AURORA_MODELO_ESPECIALISTA` pode virar `gemini-3.5-flash-lite` se
o custo pesar; os nomes já estão parametrizados no `.env.example`. Se o 503
voltar, trocar o modelo é só mudança de configuração.

## Como isso vira código na Fase 4/5

```python
from google.adk.apps._configs import ResumabilityConfig
from google.adk.apps.app import App

app = App(
    name="aurora",
    root_agent=raiz,
    resumability_config=ResumabilityConfig(is_resumable=True),  # experimental
)
runner = Runner(app=app, session_service=SqliteSessionService(db_path=...))
```

- `ResumabilityConfig` e `TOOL_CONFIRMATION` emitem `UserWarning` de
  **feature experimental**. É o motivo de D1 fixar a versão exata do ADK.
- `confirmacoes_pendentes()` (em `spike/spike_confirmacao.py`) é a derivação a
  levar para a API: os calls `adk_request_confirmation` sem `FunctionResponse` de
  mesmo id. Ela já serve de guarda do 409.
- O `ScriptedLlm` deve virar utilitário de teste em `tests/`: é o que permite
  testar os agentes no CI sem chave.
