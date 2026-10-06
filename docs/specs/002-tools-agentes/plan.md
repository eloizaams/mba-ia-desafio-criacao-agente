# Plano 002 — Tools e agentes

## Estrutura

```
src/aurora/
  config.py                          # + regulamento_path(), modelo_principal(), modelo_especialista()
  domain/
    erros.py                         # + AreaDesconhecida
    datas.py                         # data_de_texto(): AAAA-MM-DD -> date, senão DadoInvalido
    regulamento.py                   # Capitulo, dividir_em_capitulos, capitulos_relevantes
  application/
    portas.py                        # + AreaRepository.listar(), RegulamentoRepository
    reservas.py                      # ServicoReservas
    visitantes.py                    # ServicoVisitantes
    regulamento.py                   # ServicoRegulamento
  adapters/
    persistence/sqlite.py            # + listar() de áreas
    regulamento.py                   # RegulamentoArquivo: lê dados/regulamento.md (cache)
    adk/
      estado.py                      # CHAVE_APARTAMENTO + apartamento_da_sessao(tool_context)
      tools_reservas.py              # fábrica: serviço -> lista de FunctionTool
      tools_visitantes.py
      tools_regulamento.py
      agentes.py                     # construir_agentes(): aurora + reservas + visitantes + regulamento
      confirmacoes.py                # pendentes(eventos), resposta_de_confirmacao(id, confirmado)
      app.py                         # construir_app(): App com ResumabilityConfig(is_resumable=True)
```

## Ordem de trabalho

1. Domínio: `data_de_texto`, `AreaDesconhecida`, `regulamento.py` (divisão e relevância) com teste unitário.
2. Portas novas e `listar()` de áreas no adaptador SQLite.
3. Serviços de aplicação, com teste de integração sobre o SQLite real (fixture `repo` da Fase 3).
4. `RegulamentoArquivo` + `ServicoRegulamento`.
5. `estado.py` e as três fábricas de tools. Tool é fina: estado → serviço → `dict`.
6. `agentes.py` e `app.py`.
7. `confirmacoes.py`, derivado dos eventos (call `adk_request_confirmation` sem resposta de mesmo id).
8. `ScriptedLlm` por papel (`tests/support/`), substituindo o roteiro do spike.
9. Testes de integração pelo `Runner`, com `SqliteSessionService`, cobrindo os critérios de aceite.
10. Teste estrutural: nenhuma função de tool tem parâmetro de apartamento.

## Pontos de atenção

- **Assinatura do callable de `require_confirmation`.** O ADK chama `callable(**args_preparados_da_tool)`. Assinatura diferente da tool quebra com `TypeError` só em tempo de execução. Mitigação: o callable fica ao lado da tool, na mesma fábrica, e o teste de confirmação exercita o caminho.
- **Porta de saída do `ScriptedLlm`.** Toda regra que emite function call precisa da regra simétrica que detecta a resposta e fecha em texto, senão o ADK estoura o limite de 500 chamadas (`DESAFIOS.md`).
- **Tool de área desconhecida.** Sem validar a área antes de gravar, a FK do SQLite sobe como `IntegrityError` e viraria 500 (`DESAFIOS.md`). A validação é do serviço, não da tool.
- **`AgentTool` e o `state`.** O `AgentTool` copia o state do pai para a sessão interna; o agente `regulamento` não usa apartamento, então não há nada a proteger ali — mas também não deve ganhar tool de reserva nenhuma.
- **Ordem de `ruff`:** `ruff format` depois `ruff check --fix` (`DESAFIOS.md`).
