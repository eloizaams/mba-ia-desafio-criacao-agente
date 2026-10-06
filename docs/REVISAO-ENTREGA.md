# Revisão geral da entrega (pós-merge do PR #7)

Data: 2026-10-06. Base revisada: `develop` @ `efe7c66`.
Referência: `docs/enunciado-original.md` (critérios de aceite e fluxo do avaliador).

## Bloqueantes

1. **`main` não tem o projeto.** `origin/main` está em `b5a65c0` (só setup). Os PRs #3 a #7
   foram para `develop`. O entregável exige "tudo na branch `main`".
   Fix: `release/v1.0.0` → `main`, tag `v1.0.0`.
2. **Passo 1 quebra num clone limpo.** `.env.example` traz `AURORA_DB_PATH=` vazio. O
   `aurora-api` faz `load_dotenv`, a variável vira `""`, `database_path()` devolve
   `Path(".")` e o SQLite falha com `unable to open database file`. Reproduzido.
   Agravante: `aurora-restore` não lê `.env`, então com valor preenchido restore e API
   usam bancos diferentes.
   Fix: `config.py` com `os.environ.get(...) or PADRAO` (como já fazem os modelos) e
   `load_dotenv` também no `aurora-restore`. Teste de regressão.
3. **README, seção Garantias, cita trechos que não existem** (passo 15 confere):
   - G3: `App(agent=..., session_service=..., memory_service=InMemoryMemoryService())`
     não existe; o código real está em `adapters/adk/app.py` (`construir_app`/`construir_runner`).
   - G4: `def consultar(topico)` / `_selecionar` em `domain/regulamento.py` não existem;
     o real é `capitulos_relevantes` (+ `RegulamentoService.consultar` em `application/`).
   - G2: `return str(tool_context.state[CHAVE_APARTAMENTO])` difere de `state.py`.
   Fix: colar os trechos reais, com caminho correto.

## Importantes

4. **E2E com Gemini real não registrado.** Fase 5 deixou smoke pendente; Fase 7 está `[ ]`
   no PLANO. Rodar `scripts/e2e_avaliador.py` num clone limpo (pegaria o item 2).
5. Docs defasados: `CLAUDE.md` "Estado atual" (fala em Fase 5), `docs/PLANO.md` Fase 7,
   `docs/specs/004-garantias/tasks.md` (PR marcado como não aberto).

## Menores

6. README não diz que os comandos rodam da raiz do repo (`dados/` e `aurora.db` são relativos).
7. "Topologia de quatro agentes em torno de um agente raiz": são raiz + 3 especialistas.

## Conferido e OK

- ADK `==2.11.0` fixado, `uv.lock` versionado, Python ≥3.12, uv.
- `dados/` idêntico ao upstream (`be87e1d`). Nenhuma chave versionada; `.env` ignorado.
- Raiz + `reservas`/`visitantes` (sub_agents) + `regulamento` (AgentTool). Leitura/escrita só por tools.
- G1: `require_confirmation` (callable por taxa / `True`), `detalhes` = args originais, 409 antes do Runner.
- G2: nenhuma tool com parâmetro de apartamento; erros de domínio não citam apartamento/código alheio.
- G3: `SqliteSessionService` no mesmo arquivo; pendências derivadas dos eventos (sobrevivem ao reinício).
- G4: raiz sem regulamento; tool devolve ≤2 capítulos, isolada pelo AgentTool.
- G5: índice único parcial `(area, data) WHERE status='ativa'`; `IntegrityError` → `data_indisponivel`.
- Contrato: 6 rotas, status 201/200/404/409, formatos conferem.
- `ruff`, `ruff format`, `mypy`, `pytest` (110) verdes.
