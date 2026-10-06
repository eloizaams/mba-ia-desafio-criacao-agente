# Assistente Residencial Aurora

Assistente virtual construído com Google ADK para o Residencial Aurora. Moradores reservam áreas comuns, cancelam reservas, autorizam visitantes e consultam o regulamento pelo chat — com cinco garantias implementadas em código, não em prompt.

---

## Arquitetura

O assistente usa uma **topologia de quatro agentes** em torno de um agente raiz:

### Agente raiz — `aurora`

Ponto de entrada da conversa. Recebe a mensagem do morador e encaminha para o especialista correto. Não tem ferramentas de reserva nem o texto do regulamento — roteamento puro.

- **Como é acionado**: toda mensagem do morador chega a ele primeiro.
- **Por quê**: centralizar o roteamento mantém cada especialista focado; o root sem regulamento é a própria implementação da Garantia 4.

### Especialista `reservas`

Consulta, cria e cancela reservas do apartamento da sessão.

- **Como é acionado**: o root transfere quando o pedido envolve áreas comuns.
- **Modo**: `sub_agents` com transferência livre — obrigatório para a retomada de confirmação funcionar (ver `DESAFIOS.md`: `disallow_transfer_*` quebra a retomada em silêncio).
- **Por quê sub_agents**: compartilha a sessão com o root, então o `adk_request_confirmation` pendente é visível para o Runner retomar a execução.

### Especialista `visitantes`

Lista e autoriza visitantes do apartamento da sessão.

- **Como é acionado**: o root transfere quando o pedido envolve entrada de pessoas.
- **Modo**: `sub_agents`, mesma razão do `reservas`.

### Especialista `regulamento`

Responde dúvidas sobre o regulamento interno.

- **Como é acionado**: o root chama a `AgentTool(agente_regulamento)`, passando a dúvida em `request`.
- **Modo**: `AgentTool` — roda em sessão própria, isolando os eventos de regulamento da sessão principal. O docstring do ADK sugere `mode='single_turn'` + `sub_agents`, mas essa alternativa roda inline na sessão do pai, o que violaria a Garantia 4.
- **Por quê AgentTool**: garante que nenhum capítulo do regulamento vaze como evento para a sessão do morador.

### Ferramentas por especialista

| Especialista | Ferramenta | Efeito |
|---|---|---|
| `reservas` | `listar_areas` | Lê áreas do banco |
| `reservas` | `listar_minhas_reservas` | Lê reservas do apartamento da sessão |
| `reservas` | `verificar_disponibilidade` | Devolve só `livre`/`ocupada` |
| `reservas` | `reservar` | Cria reserva; exige confirmação se taxa > 0 |
| `reservas` | `cancelar_minha_reserva` | Cancela reserva do próprio apartamento |
| `visitantes` | `listar_meus_visitantes` | Lê visitantes do apartamento da sessão |
| `visitantes` | `autorizar_visitante` | Cria autorização; sempre exige confirmação |
| `regulamento` | `consultar_regulamento` | Devolve ≤ 2 capítulos relevantes |

---

## Garantias

### Garantia 1 — Cobrança ou acesso só com confirmação

**Arquivo:** `src/aurora/adapters/adk/tools_reservas.py` e `src/aurora/adapters/adk/tools_visitantes.py`

**Trecho:**
```python
# tools_reservas.py — callable avalia a taxa da área antes de executar
def _reserva_gera_cobranca(area: str, data: str, tool_context: ToolContext) -> bool:
    """Só a taxa da área decide; o modelo não influencia."""
    return servico.gera_cobranca(area)

FunctionTool(reservar, require_confirmation=_reserva_gera_cobranca)
```
```python
# tools_visitantes.py — autorizar_visitante sempre confirma
FunctionTool(autorizar_visitante, require_confirmation=True)
```

**Por que não depende do modelo**: `require_confirmation` é avaliado pelo ADK antes de executar a tool. O modelo nunca decide se a confirmação acontece — o callable lê a taxa do banco. A rota `POST /sessoes/{id}/confirmacoes` verifica se o `id` está na lista de pendências derivadas dos eventos (`src/aurora/adapters/adk/confirmacoes.py:pendentes`) antes de acionar o Runner; qualquer `id` fora dessa lista recebe `409` sem chegar ao ADK.

---

### Garantia 2 — Cada sessão pertence a um apartamento

**Arquivo:** `src/aurora/adapters/adk/sessoes.py` e `src/aurora/adapters/adk/state.py`

**Trecho:**
```python
# sessoes.py — apartamento gravado no state uma única vez
async def criar_sessao(runner: Runner, apartamento: str) -> Session:
    return await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=USUARIO,
        state={CHAVE_APARTAMENTO: apartamento},
    )
```
```python
# state.py — tools leem, nunca escrevem
def apartamento_da_sessao(tool_context: ToolContext) -> str:
    return str(tool_context.state[CHAVE_APARTAMENTO])
```

**Por que não depende do modelo**: o apartamento entra no `state` na criação da sessão e nunca é sobrescrito. Nenhuma tool recebe apartamento como parâmetro — o ADK não tem como passá-lo sem que a tool o declare. `verificar_disponibilidade` devolve só `livre`/`ocupada`, sem identificar o dono da reserva.

---

### Garantia 3 — Nada se perde no reinício

**Arquivo:** `src/aurora/adapters/adk/app.py`

**Trecho:**
```python
# app.py — sessões e eventos persistidos em SQLite
def construir_runner(banco: Path) -> Runner:
    session_service = SqliteSessionService(db_path=str(banco))
    app = App(
        agent=construir_raiz(...),
        session_service=session_service,
        memory_service=InMemoryMemoryService(),
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
    return Runner(app=app, session_service=session_service, ...)
```

**Por que não depende do modelo**: `SqliteSessionService` persiste todos os eventos no mesmo arquivo SQLite que guarda reservas e visitantes. Reiniciar o processo não apaga nada; a sessão é localizada pelo `session_id` que a rota recebe, e o Runner lê o histórico completo do banco.

---

### Garantia 4 — O regulamento é consultado, não carregado

**Arquivo:** `src/aurora/adapters/adk/agentes.py` e `src/aurora/adapters/regulamento.py`

**Trecho:**
```python
# agentes.py — regulamento como AgentTool: sessão própria, sem vazar eventos
agente_regulamento = LlmAgent(name=NOME_REGULAMENTO, ...)
return LlmAgent(
    name=NOME_RAIZ,
    ...
    sub_agents=[agente_reservas, agente_visitantes],
    tools=[AgentTool(agente_regulamento)],  # sessão isolada
)
```
```python
# domain/regulamento.py — devolve no máximo 2 capítulos por consulta
def consultar(topico: str) -> ResultadoConsulta:
    pontuados = _pontuar(topico, self._capitulos)
    return _selecionar(pontuados)  # ≤ 2 capítulos
```

**Por que não depende do modelo**: `AgentTool` executa o agente de regulamento em uma sessão separada. Os eventos dessa sessão nunca são copiados para a sessão do morador — o ADK garante isso por construção. O agente raiz não recebe o regulamento nas instruções (`INSTRUCAO_RAIZ` não menciona `regulamento.md`). A tool devolve no máximo dois capítulos, escolhidos por termos relevantes.

---

### Garantia 5 — Dois moradores, uma reserva

**Arquivo:** `src/aurora/adapters/persistence/sqlite.py` e `src/aurora/adapters/persistence/schema.py`

**Trecho:**
```sql
-- schema.py — índice único parcial: só reservas ativas competem
CREATE UNIQUE INDEX IF NOT EXISTS uq_reserva_ativa_area_data
    ON reservas (area, data) WHERE status = 'ativa';
```
```python
# sqlite.py — IntegrityError vira exceção de domínio, nunca 500
try:
    connection.execute("INSERT INTO reservas ...", params)
except sqlite3.IntegrityError as erro:
    if _AGENDA_COLUMNS in str(erro):       # violação do índice parcial (area, data)
        raise DataIndisponivel(...) from erro
    if _CODE_COLUMN in str(erro):          # colisão de código: tenta novo código
        continue
    raise
```

**Por que não depende do modelo**: a exclusividade é imposta pelo banco no instante do `INSERT`. Não importa quantas requisições simultâneas passarem pela verificação prévia — só uma consegue gravar; a outra recebe `UNIQUE constraint failed` e devolve `data_indisponivel` como resultado normal, sem 500.

---

## Como rodar

### Pré-requisitos

- Python 3.12 ou superior
- [uv](https://docs.astral.sh/uv/) instalado
- Chave do Google AI Studio (`GOOGLE_API_KEY`)

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | ✓ | Chave do Google AI Studio |
| `GOOGLE_GENAI_USE_VERTEXAI` | — | `FALSE` para AI Studio (padrão) |
| `AURORA_MODELO_PRINCIPAL` | — | Modelo do agente raiz (padrão: `gemini-3.5-flash-lite`) |
| `AURORA_MODELO_ESPECIALISTA` | — | Modelo dos especialistas (padrão: `gemini-3.5-flash-lite`) |
| `AURORA_DB_PATH` | — | Caminho do banco SQLite (padrão: `aurora.db`) |

> Se a API devolver `503`, troque o modelo por `gemini-3.5-flash` no `.env`. A disponibilidade oscila por modelo e janela de tempo.

### Instalar dependências

```bash
uv sync
```

### Restaurar dados iniciais

```bash
uv run aurora-restore
```

Para restaurar dados **e** apagar as sessões ADK (recomeçar do zero):

```bash
uv run aurora-restore --sessoes
```

### Subir a API

```bash
uv run aurora-api
```

A API sobe em `http://localhost:8000`. Para alterar host/porta, exporte `AURORA_HOST` e `AURORA_PORT` antes.

### Rodar o E2E do avaliador

Com a API no ar e os dados restaurados:

```bash
uv run python scripts/e2e_avaliador.py
```

O script percorre os 14 passos do avaliador e imprime `PASS`/`FAIL` em cada verificação. O passo 13 pausa e pede que a API seja reiniciada manualmente.

### Verificar qualidade do código

```bash
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

---

## Armazenamento

SQLite (`aurora.db` por padrão). O arquivo guarda dados do condomínio (áreas, apartamentos, reservas, visitantes) e as sessões ADK (`SqliteSessionService`). Nenhum serviço externo é necessário.

Os arquivos em `dados/` são somente leitura e representam o estado inicial; `aurora-restore` recria o banco a partir deles.
