"""Serialização de eventos para a API.

Usa exatamente o mesmo formato que o `api_server` do ADK (`adk web`), de forma
que o conteúdo completo chegue ao avaliador sem filtragem que possa mascarar
vazamento (passos 3, 4, 10, 12 da constituição).
"""

from typing import Any

from google.adk.events.event import Event


def evento_para_json(event: Event) -> dict[str, Any]:
    result: dict[str, Any] = event.model_dump(mode="json", by_alias=True, exclude_none=True)
    return result
