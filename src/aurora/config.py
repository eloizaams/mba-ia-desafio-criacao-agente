import os
from pathlib import Path

CAMINHO_BANCO_PADRAO = "aurora.db"
CAMINHO_REGULAMENTO_PADRAO = "dados/regulamento.md"
# Escolha da Fase 4: rodou o fluxo inteiro do avaliador em execução real — roteamento,
# tool calling, confirmação, retomada e AgentTool — e é o mais barato dos estáveis. O
# `gemini-3.5-flash` é a alternativa, e trocar é mudança de ambiente, não de código:
# a disponibilidade dos modelos oscila por janela (ver DESAFIOS.md).
MODELO_PADRAO = "gemini-3.5-flash-lite"


def database_path() -> Path:
    return Path(os.environ.get("AURORA_DB_PATH") or CAMINHO_BANCO_PADRAO)


def regulamento_path() -> Path:
    return Path(os.environ.get("AURORA_REGULAMENTO_PATH") or CAMINHO_REGULAMENTO_PADRAO)


def modelo_principal() -> str:
    return os.environ.get("AURORA_MODELO_PRINCIPAL") or MODELO_PADRAO


def modelo_especialista() -> str:
    return os.environ.get("AURORA_MODELO_ESPECIALISTA") or MODELO_PADRAO
