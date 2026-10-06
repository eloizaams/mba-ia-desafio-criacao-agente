"""A seleção de capítulo é determinística e é regra de domínio (Garantia 4).

Os testes rodam sobre o regulamento de verdade: é ele que o avaliador usa.
"""

from pathlib import Path

import pytest

from aurora.domain.regulamento import (
    MAXIMO_CAPITULOS,
    Capitulo,
    capitulos_relevantes,
    dividir_em_capitulos,
    termos_do_topico,
)

REGULAMENTO = Path(__file__).parents[2] / "dados" / "regulamento.md"


@pytest.fixture(scope="module")
def capitulos() -> list[Capitulo]:
    return dividir_em_capitulos(REGULAMENTO.read_text(encoding="utf-8"))


def test_divide_nos_capitulos_e_ignora_o_titulo_do_documento(capitulos: list[Capitulo]) -> None:
    assert len(capitulos) == 14
    assert capitulos[0].titulo.startswith("Capítulo I:")
    assert capitulos[0].texto.startswith("## Capítulo I:")
    assert "Regulamento Interno do Residencial" not in capitulos[0].texto


@pytest.mark.parametrize(
    ("topico", "esperado"),
    [
        ("piscina", "Capítulo IV: Piscina"),
        ("Até que horas a piscina funciona aos domingos?", "Capítulo IV: Piscina"),
        ("churrasqueira", "Capítulo VI: Salão de festas, churrasqueira e quadra"),
        ("animais de estimação", "Capítulo VIII: Animais de estimação"),
        ("mudança", "Capítulo IX: Mudanças"),
        ("lixo", "Capítulo XII: Coleta de lixo e reciclagem"),
        ("garagem", "Capítulo XI: Garagem e veículos"),
    ],
)
def test_escolhe_o_capitulo_do_assunto(
    capitulos: list[Capitulo], topico: str, esperado: str
) -> None:
    assert capitulos_relevantes(capitulos, topico)[0].titulo == esperado


def test_horario_da_piscina_no_domingo_sai_do_capitulo_escolhido(
    capitulos: list[Capitulo],
) -> None:
    """Passo 12: o fechamento aos domingos tem de estar no que a consulta devolve."""
    escolhidos = capitulos_relevantes(capitulos, "piscina domingos")

    assert len(escolhidos) == 1
    assert "das 9h às 20h" in escolhidos[0].texto


def test_palavra_comum_em_varios_capitulos_nao_arrasta_a_escolha(
    capitulos: list[Capitulo],
) -> None:
    """ "domingos" aparece em vários capítulos; o peso do título é que decide."""
    assert [c.titulo for c in capitulos_relevantes(capitulos, "piscina domingos")] == [
        "Capítulo IV: Piscina"
    ]


def test_pergunta_sobre_dois_assuntos_devolve_os_dois_capitulos(
    capitulos: list[Capitulo],
) -> None:
    escolhidos = capitulos_relevantes(capitulos, "piscina e churrasqueira")

    assert len(escolhidos) == MAXIMO_CAPITULOS
    assert "Capítulo IV: Piscina" in [c.titulo for c in escolhidos]


def test_nunca_devolve_mais_que_o_maximo(capitulos: list[Capitulo]) -> None:
    """Mesmo um tópico que casa com tudo não pode virar "regulamento inteiro"."""
    escolhidos = capitulos_relevantes(capitulos, "piscina churrasqueira garagem animais lixo obras")

    assert len(escolhidos) <= MAXIMO_CAPITULOS


def test_topico_sem_assunto_nao_devolve_capitulo(capitulos: list[Capitulo]) -> None:
    assert capitulos_relevantes(capitulos, "quais são as regras?") == []
    assert capitulos_relevantes(capitulos, "") == []


def test_termos_do_topico_descarta_palavra_generica_e_acento() -> None:
    assert termos_do_topico("Quais são as regras da Piscina aos domingos?") == [
        "piscina",
        "domingos",
    ]
