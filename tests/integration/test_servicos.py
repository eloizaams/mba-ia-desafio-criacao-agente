"""Casos de uso sobre o SQLite real: é aqui que a validação acontece antes de gravar."""

from decimal import Decimal

import pytest

from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.adapters.regulamento import RegulamentoArquivo
from aurora.application.regulamento import RegulamentoService
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService
from aurora.domain.erros import (
    AreaDesconhecida,
    DadoInvalido,
    DataIndisponivel,
    ReservaNaoEncontrada,
)
from tests.support.condominio import (
    CHURRASQUEIRA,
    DATA_DO_101,
    DATA_DO_302,
    QUADRA,
    REGULAMENTO,
    RESERVA_DO_101,
    RESERVA_DO_302,
    SALAO,
    VISITANTE_DO_302,
)


@pytest.fixture
def reservas(repo: SqliteRepository) -> ReservasService:
    return ReservasService(agenda=repo, areas=repo)


@pytest.fixture
def visitantes(repo: SqliteRepository) -> VisitantesService:
    return VisitantesService(visitantes=repo)


def test_areas_vem_do_banco_com_a_taxa(reservas: ReservasService) -> None:
    taxas = {area.id: area.taxa for area in reservas.listar_areas()}

    assert taxas[SALAO] == Decimal("150.0")
    assert taxas[QUADRA] == Decimal("0")


@pytest.mark.parametrize(("area", "cobra"), [(SALAO, True), (CHURRASQUEIRA, True), (QUADRA, False)])
def test_so_area_com_taxa_gera_cobranca(reservas: ReservasService, area: str, cobra: bool) -> None:
    """Regra de negócio 2: é esta resposta que decide a confirmação na tool."""
    assert reservas.gera_cobranca(area) is cobra


def test_area_inexistente_nao_gera_cobranca_nem_reserva(reservas: ReservasService) -> None:
    """Sem a validação, a FK do SQLite subiria como IntegrityError e viraria 500."""
    assert reservas.gera_cobranca("piscina-de-bolinhas") is False

    with pytest.raises(AreaDesconhecida):
        reservas.reservar("101", "piscina-de-bolinhas", "2030-04-20")


def test_disponibilidade_nao_depende_do_apartamento(reservas: ReservasService) -> None:
    assert reservas.disponivel(SALAO, "2030-04-20") is True
    assert reservas.disponivel(SALAO, DATA_DO_302) is False


def test_reservar_data_ocupada_levanta_data_indisponivel(reservas: ReservasService) -> None:
    with pytest.raises(DataIndisponivel):
        reservas.reservar("101", SALAO, DATA_DO_302)


def test_cancelar_resolve_o_codigo_na_lista_do_proprio_apartamento(
    reservas: ReservasService,
) -> None:
    cancelada = reservas.cancelar("101", QUADRA, DATA_DO_101)

    assert cancelada.codigo == RESERVA_DO_101
    assert reservas.minhas_reservas("101") == []


def test_cancelar_reserva_de_outro_apartamento_e_nao_encontrada(
    reservas: ReservasService,
) -> None:
    """A reserva do 302 não está na lista do 101: nem o código dela é tocado."""
    with pytest.raises(ReservaNaoEncontrada):
        reservas.cancelar("101", SALAO, DATA_DO_302)

    assert [r.codigo for r in reservas.minhas_reservas("302")] == [RESERVA_DO_302]


@pytest.mark.parametrize("data", ["20/04/2030", "2030-13-01", "amanhã", ""])
def test_data_fora_do_formato_do_contrato_e_dado_invalido(
    reservas: ReservasService, data: str
) -> None:
    with pytest.raises(DadoInvalido):
        reservas.reservar("101", SALAO, data)


def test_autorizar_visitante_grava_e_lista_so_o_apartamento(
    visitantes: VisitantesService,
) -> None:
    visitantes.autorizar("101", "Joana Ribeiro", "2030-04-21")

    assert [v.nome for v in visitantes.meus_visitantes("101")] == ["Joana Ribeiro"]
    assert [v.nome for v in visitantes.meus_visitantes("302")] == [VISITANTE_DO_302]


@pytest.mark.parametrize(("nome", "data"), [("", "2030-04-21"), ("  ", "2030-04-21")])
def test_visitante_sem_nome_nao_e_gravado(
    visitantes: VisitantesService, nome: str, data: str
) -> None:
    with pytest.raises(DadoInvalido):
        visitantes.autorizar("101", nome, data)

    assert visitantes.meus_visitantes("101") == []


def test_consulta_de_regulamento_devolve_capitulo_pertinente() -> None:
    servico = RegulamentoService(fonte=RegulamentoArquivo(REGULAMENTO))

    consulta = servico.consultar("piscina domingos")

    assert len(consulta.capitulos) == 1
    assert "das 9h às 20h" in consulta.capitulos[0].texto
    assert consulta.titulos_disponiveis == []


def test_consulta_sem_assunto_devolve_os_titulos_para_nova_tentativa() -> None:
    """A segunda tentativa é do agente, com um título na mão: nunca o documento inteiro."""
    servico = RegulamentoService(fonte=RegulamentoArquivo(REGULAMENTO))

    consulta = servico.consultar("cachorro")

    assert consulta.capitulos == []
    assert "Capítulo VIII: Animais de estimação" in consulta.titulos_disponiveis
