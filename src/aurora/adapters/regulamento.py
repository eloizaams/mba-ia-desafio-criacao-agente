"""Leitura do regulamento em disco. `dados/` é somente leitura (constituição 8)."""

from pathlib import Path

from aurora.domain.regulamento import Capitulo, dividir_em_capitulos


class RegulamentoArquivo:
    """Implementa RegulamentoRepository sobre o markdown de dados/regulamento.md.

    O arquivo é lido e dividido uma vez por instância: ele não muda em execução.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._capitulos: list[Capitulo] | None = None

    def capitulos(self) -> list[Capitulo]:
        if self._capitulos is None:
            self._capitulos = dividir_em_capitulos(self._path.read_text(encoding="utf-8"))
        return self._capitulos
