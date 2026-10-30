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
    """OpenAI-compatible chat completions provider."""

    provider_id = "openai"
    provider_label = "OpenAI"
    api_key_setting = "ai_api_key"
    model_setting = "ai_model"
    api_base_url = None

    def __init__(self):
        settings = get_settings()
        api_key = getattr(settings, self.api_key_setting)
        if not api_key:
            raise AIProviderError(
                f"{self.api_key_setting.upper()} environment variable is not set",
                provider=self.provider_id,
                recoverable=False,
            )
        client_options = {"api_key": api_key}
        if self.api_base_url:
            client_options["base_url"] = self.api_base_url
        self.client = AsyncOpenAI(**client_options)
        self.model = getattr(settings, self.model_setting)
        self.provider_name = f"{self.provider_label} ({self.model})"

    def _provider_error(self, error: Exception) -> AIProviderError:
        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            message = (
                f"{self.provider_label} rejected the API key (HTTP 401). Check that "
                f"{self.api_key_setting.upper()} is valid and that the backend loaded the updated value."
            )
        elif status_code == 403:
            message = (
                f"{self.provider_label} denied access (HTTP 403). Check account access and model permissions."
            )
        elif status_code == 404:
            message = (
                f"{self.provider_label} could not find model '{self.model}' (HTTP 404). "
                "Check the configured model name."
            )
        elif status_code == 429:
            message = (
                f"{self.provider_label} rate limit or usage quota was reached (HTTP 429). "
                "Check the account's limits and try again later."
            )
        elif status_code is not None:
            message = (
                f"{self.provider_label} rejected the request (HTTP {status_code}). "
                "Check the configured model and provider request requirements."
            )
        elif type(error).__name__ in {"APIConnectionError", "APITimeoutError"}:
            message = (
                f"Could not connect to {self.provider_label}. Check network access, DNS, "
                "and any proxy or firewall settings."
            )
        else:
            message = (
                f"{self.provider_label} request failed ({type(error).__name__}). "
                "Check backend logs for details."
            )

        return AIProviderError(
            message,
            provider=self.provider_id,
            recoverable=True,
        )

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
                    f"Empty response from {self.provider_label}",
                    provider=self.provider_id,
                )

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse {self.provider_label} response as JSON: {content[:200]}"
                )
                # Attempt to extract JSON from the response
                result = self._extract_json(content)

            return result

        except AIProviderError:
            raise
        except Exception as e:
            logger.error(
                f"{self.provider_label} API request failed.",
                extra={
                    "action": "ai_analyze",
                    "error_type": type(e).__name__,
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise self._provider_error(e) from e

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
            logger.error(
                f"{self.provider_label} chat request failed.",
                extra={
                    "action": "ai_chat",
                    "error_type": type(e).__name__,
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise self._provider_error(e) from e

    def _extract_json(self, text: str) -> dict:
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
            f"Could not parse structured response from {self.provider_label}",
            provider=self.provider_id,
        )
