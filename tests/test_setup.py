import importlib.metadata

import aurora


def test_pacote_importa() -> None:
    assert aurora.__doc__ is not None


def test_adk_fixado_na_versao_do_projeto() -> None:
    assert importlib.metadata.version("google-adk") == "2.11.0"
