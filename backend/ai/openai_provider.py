"""
OpenAI provider implementation.
"""

import json
from openai import AsyncOpenAI
from backend.ai.provider import AIProvider, AIProviderError
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI API provider (GPT-4o-mini, GPT-4o, etc.)."""

    def __init__(self):
        settings = get_settings()
        if not settings.ai_api_key:
            raise AIProviderError(
                "AI_API_KEY environment variable is not set",
                provider="openai",
                recoverable=False,
            )
        self.client = AsyncOpenAI(api_key=settings.ai_api_key)
        self.model = settings.ai_model

    async def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """Sends an analysis request and parses the JSON response."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise AIProviderError(
                    "Empty response from OpenAI",
                    provider="openai",
                )

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse OpenAI response as JSON: {content[:200]}")
                # Attempt to extract JSON from the response
                result = self._extract_json(content)

            return result

        except AIProviderError:
            raise
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", extra={"action": "ai_analyze"})
            raise AIProviderError(
                f"OpenAI API call failed: {str(e)}",
                provider="openai",
                recoverable=True,
            )

    async def chat(self, messages: list[dict]) -> str:
        """Sends a chat conversation to OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=1500,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI chat error: {e}", extra={"action": "ai_chat"})
            raise AIProviderError(
                f"OpenAI chat failed: {str(e)}",
                provider="openai",
                recoverable=True,
            )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Attempts to extract JSON from a text response."""
        import re
        # Look for JSON block in markdown code fences
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Look for raw JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise AIProviderError(
            "Could not parse structured response from OpenAI",
            provider="openai",
        )
