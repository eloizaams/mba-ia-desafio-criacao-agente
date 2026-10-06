# Assistente Residencial Aurora

Assistente virtual construído com Google ADK para o Residencial Aurora. Moradores reservam áreas comuns, cancelam reservas, autorizam visitantes e consultam o regulamento pelo chat — com cinco garantias implementadas em código, não em prompt.

---

## Arquitetura

O assistente usa um **agente raiz** e **três especialistas**:

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

**Arquivo:** `src/aurora/adapters/adk/tools_reservas.py`, `src/aurora/adapters/adk/tools_visitantes.py` e `src/aurora/adapters/api/app.py`

**Trecho:**
```python
# tools_reservas.py — o callable avalia a taxa da área antes de executar
    def _reserva_gera_cobranca(area: str, data: str, tool_context: ToolContext) -> bool:
        """Garantia 1: só a taxa da área decide se a reserva precisa de confirmação.

        O ADK invoca este callable com os mesmos argumentos de `reservar`, então a
        assinatura precisa acompanhar a da tool.
        """
        return servico.gera_cobranca(area)
```
```python
# tools_reservas.py
        FunctionTool(reservar, require_confirmation=_reserva_gera_cobranca),
```
```python
# tools_visitantes.py — autorizar_visitante sempre confirma
        FunctionTool(autorizar_visitante, require_confirmation=True),
```
```python
# api/app.py (post_confirmacao) — só aceita id pendente nesta sessão, antes de chamar o Runner
        sessao = await _exigir_sessao(session_id)
        # Guarda do 409: id fora da lista levanta ValueError no Runner (DESAFIOS.md)
        if not any(p.id == corpo.id for p in pendentes(sessao.events)):
            raise HTTPException(
                status_code=409, detail="Confirmação não encontrada ou já respondida"
            )
        turno = await confirmar(runner, session_id, corpo.id, corpo.confirmado)
```

**Por que não depende do modelo**: `require_confirmation` é avaliado pelo ADK antes de executar a tool. O modelo nunca decide se a confirmação acontece — o callable lê a taxa do banco. A rota `POST /sessoes/{id}/confirmacoes` verifica se o `id` está na lista de pendências derivadas dos eventos (`src/aurora/adapters/adk/confirmacoes.py:pendentes`) antes de acionar o Runner; qualquer `id` fora dessa lista — inclusive o de uma confirmação já respondida, que deixa de estar pendente — recebe `409` sem chegar ao ADK. Mensagem do morador dizendo "já confirmei" não passa por essa rota, então não aprova nada.

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
    apartamento = tool_context.state.get(CHAVE_APARTAMENTO)
    if not isinstance(apartamento, str) or not apartamento:
        raise SessaoSemApartamento(f"state['{CHAVE_APARTAMENTO}'] ausente ou inválido")
    return apartamento
```

**Por que não depende do modelo**: o apartamento entra no `state` na criação da sessão e nunca é sobrescrito. Nenhuma tool recebe apartamento como parâmetro — o ADK não tem como passá-lo sem que a tool o declare. `verificar_disponibilidade` devolve só `livre`/`ocupada`, sem identificar o dono da reserva.

---

### Garantia 3 — Nada se perde no reinício

**Arquivo:** `src/aurora/adapters/adk/app.py` (`construir_runner`)

**Trecho:**
```python
# app.py — sessões e eventos persistidos num SQLite ao lado do banco do condomínio (`aurora.db.sessoes`)
return Runner(
    app=construir_app(banco=caminho, regulamento=regulamento, modelo=modelo),
    session_service=SqliteSessionService(db_path=str(sessions_path(caminho))),
)
```
```python
# app.py (construir_app) — retomada explícita da confirmação
    return App(
        name=NOME_RAIZ,
        root_agent=raiz,
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
```

**Por que não depende do modelo**: `SqliteSessionService` persiste todos os eventos em um arquivo SQLite próprio (`aurora.db.sessoes`), separado do que guarda reservas e visitantes. Reiniciar o processo não apaga nada; a sessão é localizada pelo `session_id` que a rota recebe, e o Runner lê o histórico completo do banco.

---

### Garantia 4 — O regulamento é consultado, não carregado

**Arquivo:** `src/aurora/adapters/adk/agentes.py` e `src/aurora/domain/regulamento.py`

**Trecho:**
```python
# agentes.py (construir_raiz) — regulamento como AgentTool: sessão própria, sem vazar eventos
    return LlmAgent(
        name=NOME_RAIZ,
        model=modelo(NOME_RAIZ),
        description="Assistente do Residencial Aurora: roteia o pedido do morador.",
        instruction=INSTRUCAO_RAIZ,
        sub_agents=[agente_reservas, agente_visitantes],
        tools=[AgentTool(agente_regulamento)],
    )
```
```python
# domain/regulamento.py (capitulos_relevantes) — no máximo dois capítulos, por pontuação de termos
    pontuados.sort(key=lambda par: par[0], reverse=True)
    melhor = pontuados[0][0]
    corte = melhor * FRACAO_QUASE_EMPATE
    return [capitulo for pontos, capitulo in pontuados[:MAXIMO_CAPITULOS] if pontos >= corte]
```

**Por que não depende do modelo**: `AgentTool` executa o agente de regulamento em uma sessão separada. Os eventos dessa sessão nunca são copiados para a sessão do morador — o ADK garante isso por construção. O agente raiz não recebe o regulamento nas instruções (`INSTRUCAO_RAIZ` não menciona `regulamento.md`). A tool (`consultar_regulamento`, via `capitulos_relevantes`) devolve no máximo dois capítulos, escolhidos por termos relevantes.

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
# sqlite.py (gravar_reserva) — IntegrityError vira exceção de domínio, nunca 500
            try:
                with self._connection() as connection:
                    connection.execute(
                        "INSERT INTO reservas (codigo, apartamento, area, data, status) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (codigo, apartamento, area, data.isoformat(), StatusReserva.ATIVA),
                    )
            except sqlite3.IntegrityError as erro:
                mensagem = str(erro)
                if _AGENDA_COLUMNS in mensagem:
                    raise DataIndisponivel(f"{area} em {data.isoformat()}") from erro
                if _CODE_COLUMN in mensagem:
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

> Todos os comandos abaixo rodam **da raiz do repositório**: `dados/` e `aurora.db` são caminhos relativos.

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

Pare a API antes: apagar o arquivo de sessões com ela no ar deixa o processo preso ao arquivo antigo.

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

SQLite (`aurora.db` por padrão). `aurora.db` guarda os dados do condomínio (áreas, apartamentos, reservas, visitantes); `aurora.db.sessoes`, as sessões ADK (`SqliteSessionService`). Nenhum serviço externo é necessário.

Os arquivos em `dados/` são somente leitura e representam o estado inicial; `aurora-restore` recria o banco a partir deles.
