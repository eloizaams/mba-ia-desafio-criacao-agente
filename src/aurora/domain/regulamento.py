"""Regulamento em capítulos e a escolha do capítulo pertinente.

Regra da Garantia 4: a consulta devolve o capítulo que trata do assunto, não o
documento. A escolha é determinística e fica aqui, no domínio — o modelo só
informa o tópico.
"""

import re
import unicodedata
from dataclasses import dataclass

MARCA_CAPITULO = re.compile(r"^## (.+)$", re.MULTILINE)

# O título é o resumo do assunto do capítulo: um termo que casa com ele vale muito
# mais que o mesmo termo perdido no corpo, onde palavras comuns ("domingos",
# "convidados") aparecem em quase todo capítulo.
PESO_TITULO = 10
PESO_CORPO = 1

# Em quase-empate o assunto pode estar partido em dois capítulos ("piscina e
# churrasqueira"). Abaixo disso, o segundo capítulo é só ruído.
FRACAO_QUASE_EMPATE = 0.6
MAXIMO_CAPITULOS = 2

TAMANHO_MINIMO_TERMO = 4

# Palavras genéricas de pergunta: casam com qualquer capítulo e não indicam assunto.
TERMOS_IGNORADOS = frozenset(
    {
        "ainda",
        "algum",
        "alguma",
        "antes",
        "apartamento",
        "aqui",
        "artigo",
        "capitulo",
        "coisa",
        "como",
        "condominio",
        "deve",
        "devo",
        "dias",
        "esta",
        "estao",
        "funciona",
        "hora",
        "horario",
        "horarios",
        "horas",
        "mais",
        "meu",
        "minha",
        "morador",
        "moradores",
        "onde",
        "para",
        "pela",
        "pelo",
        "pode",
        "podem",
        "posso",
        "quais",
        "qual",
        "quando",
        "quanto",
        "quantos",
        "regimento",
        "regra",
        "regras",
        "regulamento",
        "residencial",
        "sobre",
        "tudo",
    }
)


@dataclass(frozen=True)
class Capitulo:
    titulo: str
    texto: str


def dividir_em_capitulos(markdown: str) -> list[Capitulo]:
    """Quebra o regulamento nos títulos de nível 2. O que vem antes do primeiro não é capítulo."""
    marcas = list(MARCA_CAPITULO.finditer(markdown))
    capitulos = []
    for indice, marca in enumerate(marcas):
        fim = marcas[indice + 1].start() if indice + 1 < len(marcas) else len(markdown)
        capitulos.append(
            Capitulo(titulo=marca.group(1).strip(), texto=markdown[marca.start() : fim].strip())
        )
    return capitulos


def capitulos_relevantes(capitulos: list[Capitulo], topico: str) -> list[Capitulo]:
    """Capítulos que tratam do tópico, do mais pertinente para o menos. Vazio se nada casar."""
    termos = termos_do_topico(topico)
    if not termos:
        return []

    pontuados = [(_pontuar(capitulo, termos), capitulo) for capitulo in capitulos]
    pontuados = [(pontos, capitulo) for pontos, capitulo in pontuados if pontos > 0]
    if not pontuados:
        return []

    pontuados.sort(key=lambda par: par[0], reverse=True)
    melhor = pontuados[0][0]
    corte = melhor * FRACAO_QUASE_EMPATE
    return [capitulo for pontos, capitulo in pontuados[:MAXIMO_CAPITULOS] if pontos >= corte]


def termos_do_topico(topico: str) -> list[str]:
    """Termos que identificam assunto: sem acento, sem palavra curta, sem palavra genérica."""
    palavras = re.findall(r"\w+", _normalizar(topico))
    return [
        palavra
        for palavra in dict.fromkeys(palavras)
        if len(palavra) >= TAMANHO_MINIMO_TERMO and palavra not in TERMOS_IGNORADOS
    ]


def _pontuar(capitulo: Capitulo, termos: list[str]) -> int:
    titulo = _normalizar(capitulo.titulo)
    corpo = _normalizar(capitulo.texto)
    no_titulo = sum(1 for termo in termos if _ocorre(termo, titulo))
    no_corpo = sum(1 for termo in termos if _ocorre(termo, corpo))
    return PESO_TITULO * no_titulo + PESO_CORPO * no_corpo


def _ocorre(termo: str, texto: str) -> bool:
    # O plural do morador não precisa casar com o singular do regulamento, nem o contrário.
    return termo in texto or termo.rstrip("s") in texto


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(letra for letra in sem_acento if not unicodedata.combining(letra))
