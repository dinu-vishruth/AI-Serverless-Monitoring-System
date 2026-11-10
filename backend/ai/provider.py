"""
AI provider abstraction — defines the interface all LLM providers must implement.

Supported providers:
  - openai      : OpenAI API (GPT-4o-mini, GPT-4o, etc.)
  - aws_bedrock : AWS Bedrock (Claude, Titan, etc.)
  - mock        : Local incident-analysis simulation (chat is disabled)
"""

from abc import ABC, abstractmethod
from typing import List
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AIProvider(ABC):
    """Abstract base class for AI/LLM providers."""
    provider_name: str = "base"

    @abstractmethod
    async def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Sends a prompt to the LLM and returns a structured response.
        """
        pass

    @abstractmethod
    async def chat(self, messages: List[dict]) -> str:
        """
        Sends a chat conversation to the LLM.
        """
        pass


class AIProviderError(Exception):
    """Raised when an AI provider call fails."""

    def __init__(self, message: str, provider: str = "unknown", recoverable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable


def get_ai_provider() -> AIProvider:
    """
    Returns the explicitly configured provider without silently substituting a mock.
    """
    settings = get_settings()
    provider_name = settings.ai_provider.lower()

    if provider_name == "openai":
        if not settings.ai_api_key:
            raise AIProviderError(
                "AI_API_KEY is not configured. Set it in the backend environment to use OpenAI.",
                provider="openai",
                recoverable=False,
            )
        try:
            from backend.ai.openai_provider import OpenAIProvider
            return OpenAIProvider()
        except Exception as e:
            logger.error("Failed to initialize OpenAI provider.", extra={"action": "ai_provider_init"})
            raise AIProviderError(
                "Could not initialize OpenAI. Verify the backend dependencies and configuration.",
                provider="openai",
                recoverable=False,
            ) from e
    elif provider_name == "groq":
        if not settings.groq_api_key and not settings.groq_secret_arn:
            raise AIProviderError(
                "GROQ_API_KEY is not configured. Set it in the backend environment to use Groq.",
                provider="groq",
                recoverable=False,
            )
        try:
            from backend.ai.groq_provider import GroqProvider
            return GroqProvider()
        except Exception as e:
            logger.error("Failed to initialize Groq provider.", extra={"action": "ai_provider_init"})
            raise AIProviderError(
                "Could not initialize Groq. Verify the backend dependencies and configuration.",
                provider="groq",
                recoverable=False,
            ) from e

    elif provider_name == "aws_bedrock":
        try:
            from backend.ai.aws_provider import AWSBedrockProvider
            return AWSBedrockProvider()
        except Exception as e:
            logger.error("Failed to initialize AWS Bedrock provider.", extra={"action": "ai_provider_init"})
            raise AIProviderError(
                "Could not initialize AWS Bedrock. Verify the backend dependencies, AWS credentials, and configuration.",
                provider="aws_bedrock",
                recoverable=False,
            ) from e

    if provider_name == "mock":
        raise AIProviderError("Mock AI is disabled; configure a real provider", provider="mock", recoverable=False)

    raise AIProviderError(
        f"Unsupported AI_PROVIDER '{settings.ai_provider}'. Choose groq, openai, aws_bedrock, or mock.",
        provider=provider_name,
        recoverable=False,
    )
