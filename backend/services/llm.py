"""Provider-neutral async JSON generation backed by the Groq API."""

from __future__ import annotations

import json
from typing import Any

from groq import AsyncGroq

from backend.config import settings


class GroqClient:
    """Small boundary that keeps Groq client details out of agents."""

    def __init__(self, client: AsyncGroq | None = None) -> None:
        self._client = client

    def _get_client(self) -> AsyncGroq:
        if self._client is None:
            self._client = AsyncGroq(api_key=settings.groq_api_key)
        return self._client

    async def json_completion(
        self, *, model: str, system_prompt: str, prompt: str
    ) -> dict[str, Any]:
        response = await self._get_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned an empty response")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Groq JSON response must be an object")
        return parsed
