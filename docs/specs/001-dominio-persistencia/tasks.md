# Tarefas 001 — Domínio e persistência

- [x] Domínio: `Area` (taxa em `Decimal`), `Reserva`, `Visitante`, `gerar_codigo_reserva`, erros
- [x] Teste: domínio não importa ADK, FastAPI, SQLite nem `aurora.adapters`
- [x] Portas em `application/portas.py`
- [x] Schema com índice único parcial `(area, data) WHERE status='ativa'` e `UNIQUE(codigo)`
- [x] `SqliteRepository`: agenda, gravação com tradução de `IntegrityError`, cancelamento por apartamento, visitantes, áreas
- [x] Nova tentativa em colisão de código (até 5)
- [x] `aurora-restore` com dados da conversa desfeitos, idempotente (conteúdo e ids), com `--dados` e `--banco`
- [x] Testes de integração: seed, cancelamento, código não reaproveitado, colisão, restore
- [x] Disputa concorrente: 20 threads, 1 vence (estável em 15 rodadas)
- [x] Prova de contraste como teste: sem o índice, "checar e gravar" deixa as 20 gravarem (`test_sem_o_indice_checar_e_gravar_deixa_todos_gravarem`)
- [x] `Visitante` recusa nome vazio (`DadoInvalido`)
- [x] `ruff check`, `ruff format --check`, `mypy`, `pytest` verdes (26 testes)
- [ ] Limpeza das sessões ADK pelo `aurora-restore --sessoes`: adiada para a Fase 5
