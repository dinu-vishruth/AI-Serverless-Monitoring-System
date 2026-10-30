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


class MockAIProvider(AIProvider):
    """
    Local incident-analysis simulation used for testing without an LLM.
    """
    provider_name: str = "AI-Serverless-LocalEngine"

    async def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """Simulates structured telemetry analysis."""
        return {
            "incident_summary": (
                "Telemetry telemetry analysis shows abnormal latency escalation exceeding configured thresholds. "
                "The Isolation Forest flagged multidimensional variance with anomalous error distribution."
            ),
            "observed_facts": [
                "Response time deviated by >200% above historical baseline moving average",
                "Upstream gateway reported increased connection latency and occasional 5xx codes",
                "Isolation Forest anomaly detector flagged high outlier score"
            ],
            "possible_causes": [
                "Upstream downstream dependency saturation or rate limiting",
                "Serverless cold start concurrency burst or thread pool saturation",
                "Network latency degradation or intermittent DNS resolution delay"
            ],
            "impact": [
                "Degraded user experience and possible request retry storms",
                "Higher error rate if downstream timeouts continue"
            ],
            "recommended_actions": [
                "Inspect CloudWatch Lambda logs for unhandled timeouts and exceptions",
                "Verify database provisioned throughput and connection pool health",
                "Review recent application deployments or traffic spikes"
            ],
            "confidence": "high",
        }

    async def chat(self, messages: List[dict]) -> str:
        """Prevents the mock provider from presenting canned text as an LLM answer."""
        raise AIProviderError(
            "The chat assistant requires a real LLM. Configure AI_PROVIDER=groq with "
            "GROQ_API_KEY, AI_PROVIDER=openai with AI_API_KEY, or aws_bedrock with valid AWS credentials.",
            provider="mock",
            recoverable=False,
        )


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
        if not settings.groq_api_key:
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
        return MockAIProvider()

    raise AIProviderError(
        f"Unsupported AI_PROVIDER '{settings.ai_provider}'. Choose groq, openai, aws_bedrock, or mock.",
        provider=provider_name,
        recoverable=False,
    )
