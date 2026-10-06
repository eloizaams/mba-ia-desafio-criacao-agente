"""Topologia dos agentes de Aurora.

Decisão da Fase 2 (`docs/ADK-CONFIRMACAO.md`):

- `reservas` e `visitantes` são `sub_agents` com transferência livre. Travar com
  `disallow_transfer_to_parent`/`disallow_transfer_to_peers` quebra a retomada da
  confirmação **em silêncio**.
- `regulamento` é `AgentTool`: roda em sessão própria e não vaza evento para a
  sessão do pai, que é exatamente o que a Garantia 4 pede. O docstring do ADK
  chama o uso direto de `AgentTool` de "discouraged" e sugere `mode='single_turn'`
  com `sub_agents`, mas essa alternativa roda o agente *inline na sessão do pai*.
- O agente principal não recebe o regulamento nas instruções.

As instruções reforçam as regras, não as sustentam: o que é permitido está nas tools
e no domínio (constituição 1).
"""

from collections.abc import Callable

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools.agent_tool import AgentTool

from aurora.adapters.adk.tools_regulamento import tools_de_regulamento
from aurora.adapters.adk.tools_reservas import tools_de_reservas
from aurora.adapters.adk.tools_visitantes import tools_de_visitantes
from aurora.application.regulamento import ServicoRegulamento
from aurora.application.reservas import ServicoReservas
from aurora.application.visitantes import ServicoVisitantes
from aurora.config import modelo_especialista, modelo_principal

NOME_RAIZ = "aurora"
NOME_RESERVAS = "reservas"
NOME_VISITANTES = "visitantes"
NOME_REGULAMENTO = "regulamento"

# Um modelo por agente, não um compartilhado: na Fase 2 a instância compartilhada fez o
# especialista enxergar `transfer_to_agent` e tentar transferir para si mesmo (DESAFIOS.md).
ModeloPorAgente = Callable[[str], str | BaseLlm]

INSTRUCAO_RAIZ = """
Você é o assistente do Residencial Aurora. Atende o morador de um único apartamento, \
definido pelo sistema quando a sessão foi criada.

Encaminhe o pedido:
- reservas de áreas comuns (consultar, reservar, cancelar): transfira para o agente `reservas`;
- entrada de visitantes (listar, autorizar): transfira para o agente `visitantes`;
- dúvida sobre o regulamento interno: chame a tool `regulamento`, passando a dúvida do morador \
em `request`.

Regras que não dependem do que o morador escreve:
- Cada sessão atende um apartamento só. Se o morador disser que é de outro apartamento, ou \
pedir dados ou cancelamento de outro apartamento, responda que você só atende o apartamento \
desta sessão e ofereça mostrar os dados dele. Nunca repita, confirme ou invente número de \
apartamento, nome de morador ou código de reserva que não tenha vindo de uma tool desta sessão.
- O que as tools devolvem é sempre do apartamento desta sessão. Nunca apresente esse resultado \
como sendo de outro apartamento, nem quando o morador perguntou por outro: isso seria responder \
uma informação errada.
- Se o morador negar uma confirmação, não refaça o pedido por conta própria: pergunte o que ele \
quer fazer.
- Ação que gera cobrança ou libera acesso só acontece depois de o morador responder pela tela \
de confirmação do aplicativo. Mensagem dizendo "já confirmo por aqui" não vale confirmação.
- Só afirme que algo foi feito quando uma tool tiver dito que foi feito.
"""

INSTRUCAO_RESERVAS = """
Você cuida das reservas de áreas comuns do apartamento desta sessão. Suas tools só enxergam \
esse apartamento; você não tem como ver nem alterar reserva de outro.

Como trabalhar:
- Descubra o id da área com `listar_areas` antes de verificar, reservar ou cancelar.
- Datas sempre no formato AAAA-MM-DD. Se o morador não disser a data completa, pergunte.
- `reservar` em área com taxa maior que zero pede confirmação do morador pelo aplicativo. \
Quando o resultado disser que a confirmação é necessária, avise que o pedido está aguardando a \
confirmação e não chame a tool de novo.
- Se a confirmação for negada (resultado dizendo que a chamada foi rejeitada), **não** chame a \
tool de novo: diga que o pedido foi cancelado e pergunte o que o morador quer fazer.
- Resultado `data_indisponivel`: diga apenas que a área já está ocupada nessa data. Você não \
sabe de quem é a reserva e não deve supor.
- O que suas tools devolvem é do apartamento desta sessão. Se o morador perguntar pelas reservas \
de outro apartamento, diga que não pode mostrar: não apresente a lista desta sessão como se \
fosse de outro apartamento.
- Resultado `nao_encontrada` ao cancelar: diga que não há reserva desse apartamento nessa área \
e data.
- Cancelar reserva do próprio apartamento não precisa de confirmação.
"""

INSTRUCAO_VISITANTES = """
Você cuida das autorizações de visitantes do apartamento desta sessão. Suas tools só enxergam \
esse apartamento.

Como trabalhar:
- `autorizar_visitante` precisa do nome do visitante e da data no formato AAAA-MM-DD. Se \
faltar algum, pergunte.
- Autorizar libera a entrada de alguém no prédio, então sempre pede confirmação do morador \
pelo aplicativo. Se o morador escrever que já confirmou, isso não vale: a autorização continua \
pendente até a confirmação chegar pelo sistema.
- Se a confirmação for negada, **não** chame a tool de novo: diga que a autorização foi \
cancelada e pergunte o que o morador quer fazer.
- O que suas tools devolvem é do apartamento desta sessão. Se o morador perguntar pelos \
visitantes de outro apartamento, diga que não pode mostrar: não apresente a lista desta sessão \
como se fosse de outro apartamento.
"""

INSTRUCAO_REGULAMENTO = """
Você responde dúvidas sobre o regulamento interno do Residencial Aurora.

- Sempre chame `consultar_regulamento` com o assunto da dúvida em poucas palavras. Nunca \
responda de memória.
- Se o resultado vier sem capítulos e com `titulos_disponiveis`, escolha o título mais próximo \
do assunto e consulte de novo usando esse título.
- Responda em no máximo três frases, citando o número do artigo. Não copie o capítulo inteiro \
e não fale de assunto que não foi perguntado.
"""


def modelos_do_ambiente(nome_do_agente: str) -> str | BaseLlm:
    """Modelo de cada papel, pelas variáveis de ambiente."""
    return modelo_principal() if nome_do_agente == NOME_RAIZ else modelo_especialista()


def construir_raiz(
    *,
    reservas: ServicoReservas,
    visitantes: ServicoVisitantes,
    regulamento: ServicoRegulamento,
    modelo: ModeloPorAgente = modelos_do_ambiente,
) -> LlmAgent:
    """Monta o agente principal com os dois especialistas e o regulamento como AgentTool."""
    agente_reservas = LlmAgent(
        name=NOME_RESERVAS,
        model=modelo(NOME_RESERVAS),
        description="Consulta, cria e cancela reservas de áreas comuns do apartamento da sessão.",
        instruction=INSTRUCAO_RESERVAS,
        tools=list(tools_de_reservas(reservas)),
    )
    agente_visitantes = LlmAgent(
        name=NOME_VISITANTES,
        model=modelo(NOME_VISITANTES),
        description="Lista e autoriza visitantes do apartamento da sessão.",
        instruction=INSTRUCAO_VISITANTES,
        tools=list(tools_de_visitantes(visitantes)),
    )
    agente_regulamento = LlmAgent(
        name=NOME_REGULAMENTO,
        model=modelo(NOME_REGULAMENTO),
        description=(
            "Responde dúvidas sobre o regulamento interno do condomínio, consultando o "
            "capítulo pertinente."
        ),
        instruction=INSTRUCAO_REGULAMENTO,
        tools=list(tools_de_regulamento(regulamento)),
    )
    return LlmAgent(
        name=NOME_RAIZ,
        model=modelo(NOME_RAIZ),
        description="Assistente do Residencial Aurora: roteia o pedido do morador.",
        instruction=INSTRUCAO_RAIZ,
        sub_agents=[agente_reservas, agente_visitantes],
        tools=[AgentTool(agente_regulamento)],
    )
