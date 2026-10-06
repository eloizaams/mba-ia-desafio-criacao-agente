import importlib.metadata


def test_adk_fixado_na_versao_do_projeto() -> None:
    assert importlib.metadata.version("google-adk") == "2.11.0"
