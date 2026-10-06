# Plano 001 — Domínio e persistência

## Estrutura

```
src/aurora/
  config.py                          # AURORA_DB_PATH
  domain/
    erros.py                         # DominioError, DataIndisponivel, ReservaNaoEncontrada
    area.py                          # Area (taxa em Decimal, gera_cobranca)
    reserva.py                       # Reserva, StatusReserva (ativa/cancelada)
    visitante.py                     # Visitante
    codigo.py                        # gerar_codigo_reserva()
  application/
    portas.py                        # Protocols: AgendaRepository, ReservaRepository, VisitanteRepository, AreaRepository
  adapters/
    persistence/
      schema.py                      # DDL: areas, apartamentos, reservas, visitantes
      sqlite.py                      # implementa as portas
      restore.py                     # carrega dados/*.json; entrypoint aurora-restore
```

## Ordem de trabalho

1. Domínio (testes unitários primeiro): `Area`, `Reserva.cancelar`, `Visitante`, `gerar_codigo_reserva`.
2. Portas em `application/portas.py`.
3. Schema + conexão SQLite (`WAL`, `busy_timeout`, `foreign_keys=ON`).
4. Repositórios: leitura da agenda, gravação de reserva com tradução de `IntegrityError`, cancelamento por apartamento, visitantes, áreas.
5. `aurora-restore`: em uma transação, apaga as tabelas de estado e recarrega dos JSON. `dados/` só é lido.
6. Teste de concorrência com `ThreadPoolExecutor` e arquivo temporário.
7. `[project.scripts]` no `pyproject.toml`.

## Riscos

- **Mensagem do SQLite como contrato.** Distinguir os dois `UNIQUE` pelo texto do erro é frágil entre versões. Mitigação: teste de integração que força cada caso. Se a versão do Python mudar, o teste acusa.
- **Sync dentro de handler async (Fase 5).** `sqlite3` bloqueia. Mitigação para a Fase 5: `asyncio.to_thread` nas rotas. Decidido aqui para não reabrir a escolha depois.
