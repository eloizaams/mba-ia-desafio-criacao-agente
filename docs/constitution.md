# Constituição do projeto — Assistente Residencial Aurora

Princípios não negociáveis. Toda spec, plano e PR deve respeitá-los.

1. **O modelo decide o caminho, o código decide o que é permitido.** Nenhuma regra de negócio ou garantia vive só no prompt.
2. **Apartamento vem da sessão.** Nenhuma tool recebe apartamento como argumento do modelo; usa `tool_context.state`, gravado na criação da sessão.
3. **Domínio sem framework.** `domain/` não importa ADK, FastAPI nem SQLite. Regras testáveis sem LLM.
4. **Exclusividade no banco.** Unicidade (reserva ativa por área/data, código de reserva) é garantida por constraint no SQLite, não por checagem prévia.
5. **Nada vaza.** Tools nunca devolvem dados de outro apartamento: agenda alheia vira apenas `livre`/`ocupada`.
6. **Regulamento sob demanda.** Agente principal não carrega o regulamento; consulta devolve só o capítulo pertinente, em contexto isolado.
7. **Contrato da API é lei.** Caminhos, campos e status exatamente como no enunciado.
8. **`dados/` é imutável.** Estado inicial só é lido; mudanças vão para o banco.
9. **Rastreabilidade.** Cada spec referencia as garantias/passos do avaliador que cobre; o README aponta arquivo e trecho de cada garantia.
10. **Fluxo de trabalho.** Git Flow (`feature/*` → `develop` → `release/*` → `main` + tag), Conventional Commits, PR com revisão (`code-review`) antes do merge.

## Convenções
- Python 3.12+, uv, ADK com versão exata fixada.
- Nomes de domínio em português (`Reserva`, `apartamento`); termos técnicos em inglês (`repository`, `service`).
- ruff + mypy (strict no `domain/` e `application/`), pytest, pre-commit, CI no GitHub Actions.
