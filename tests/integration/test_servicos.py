"""Casos de uso sobre o SQLite real: é aqui que a validação acontece antes de gravar."""

from decimal import Decimal

import pytest

from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.adapters.regulamento import RegulamentoArquivo
from aurora.application.regulamento import ServicoRegulamento
from aurora.application.reservas import ServicoReservas
from aurora.application.visitantes import ServicoVisitantes
from aurora.domain.erros import (
    AreaDesconhecida,
    DadoInvalido,
    DataIndisponivel,
    ReservaNaoEncontrada,
)
from tests.integration.conftest import REGULAMENTO

SALAO = "salao-de-festas"
QUADRA = "quadra"


@pytest.fixture
def reservas(repo: SqliteRepository) -> ServicoReservas:
    return ServicoReservas(agenda=repo, areas=repo)


@pytest.fixture
def visitantes(repo: SqliteRepository) -> ServicoVisitantes:
    return ServicoVisitantes(visitantes=repo)


def test_areas_vem_do_banco_com_a_taxa(reservas: ServicoReservas) -> None:
    taxas = {area.id: area.taxa for area in reservas.listar_areas()}

    assert taxas[SALAO] == Decimal("150.0")
    assert taxas[QUADRA] == Decimal("0")


@pytest.mark.parametrize(
    ("area", "cobra"), [(SALAO, True), ("churrasqueira", True), (QUADRA, False)]
)
def test_so_area_com_taxa_gera_cobranca(reservas: ServicoReservas, area: str, cobra: bool) -> None:
    """Regra de negócio 2: é esta resposta que decide a confirmação na tool."""
    assert reservas.gera_cobranca(area) is cobra


def test_area_inexistente_nao_gera_cobranca_nem_reserva(reservas: ServicoReservas) -> None:
    """Sem a validação, a FK do SQLite subiria como IntegrityError e viraria 500."""
    assert reservas.gera_cobranca("piscina-de-bolinhas") is False

    with pytest.raises(AreaDesconhecida):
        reservas.reservar("101", "piscina-de-bolinhas", "2030-04-20")


def test_disponibilidade_nao_depende_do_apartamento(reservas: ServicoReservas) -> None:
    assert reservas.disponivel(SALAO, "2030-04-20") is True
    assert reservas.disponivel(SALAO, "2030-03-16") is False


def test_reservar_data_ocupada_levanta_data_indisponivel(reservas: ServicoReservas) -> None:
    with pytest.raises(DataIndisponivel):
        reservas.reservar("101", SALAO, "2030-03-16")


def test_cancelar_resolve_o_codigo_na_lista_do_proprio_apartamento(
    reservas: ServicoReservas,
) -> None:
    cancelada = reservas.cancelar("101", QUADRA, "2030-03-09")

    assert cancelada.codigo == "RSV-1377"
    assert reservas.minhas_reservas("101") == []


def test_cancelar_reserva_de_outro_apartamento_e_nao_encontrada(
    reservas: ServicoReservas,
) -> None:
    """A reserva do 302 não está na lista do 101: nem o código dela é tocado."""
    with pytest.raises(ReservaNaoEncontrada):
        reservas.cancelar("101", SALAO, "2030-03-16")

    assert [r.codigo for r in reservas.minhas_reservas("302")] == ["RSV-4821"]


@pytest.mark.parametrize("data", ["20/04/2030", "2030-13-01", "amanhã", ""])
def test_data_fora_do_formato_do_contrato_e_dado_invalido(
    reservas: ServicoReservas, data: str
) -> None:
    with pytest.raises(DadoInvalido):
        reservas.reservar("101", SALAO, data)


def test_autorizar_visitante_grava_e_lista_so_o_apartamento(
    visitantes: ServicoVisitantes,
) -> None:
    visitantes.autorizar("101", "Joana Ribeiro", "2030-04-21")

    assert [v.nome for v in visitantes.meus_visitantes("101")] == ["Joana Ribeiro"]
    assert [v.nome for v in visitantes.meus_visitantes("302")] == ["Marina Duarte"]


@pytest.mark.parametrize(("nome", "data"), [("", "2030-04-21"), ("  ", "2030-04-21")])
def test_visitante_sem_nome_nao_e_gravado(
    visitantes: ServicoVisitantes, nome: str, data: str
) -> None:
    with pytest.raises(DadoInvalido):
        visitantes.autorizar("101", nome, data)

    assert visitantes.meus_visitantes("101") == []


def test_consulta_de_regulamento_devolve_capitulo_pertinente() -> None:
    servico = ServicoRegulamento(fonte=RegulamentoArquivo(REGULAMENTO))

    consulta = servico.consultar("piscina domingos")

    assert len(consulta.capitulos) == 1
    assert "das 9h às 20h" in consulta.capitulos[0].texto
    assert consulta.titulos_disponiveis == []


def test_consulta_sem_assunto_devolve_os_titulos_para_nova_tentativa() -> None:
    """A segunda tentativa é do agente, com um título na mão: nunca o documento inteiro."""
    servico = ServicoRegulamento(fonte=RegulamentoArquivo(REGULAMENTO))

    consulta = servico.consultar("cachorro")

    assert consulta.capitulos == []
    assert "Capítulo VIII: Animais de estimação" in consulta.titulos_disponiveis
