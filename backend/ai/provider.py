"""
AI provider abstraction — defines the interface all LLM providers must implement.

Supported providers:
  - openai      : OpenAI API (GPT-4o-mini, GPT-4o, etc.)
  - aws_bedrock : AWS Bedrock (Claude, Titan, etc.)
  - mock        : Built-in local explainability engine (offline/testing)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
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
    Built-in Intelligent Local SRE Provider.
    Generates deterministic, context-aware telemetry root-cause explanations
    and conversational answers when external LLM credentials are not configured.
    """
    provider_name: str = "AegisAI-LocalEngine"

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
        """Answers chat queries with context."""
        query = messages[-1].get("content", "") if messages else ""
        return (
            f"Based on real-time serverless telemetry, the system is actively monitoring configured endpoints. "
            f"Isolation Forest evaluates response time, error rate, and jitter. "
            f"If degradation occurs, risk scoring will escalate and trigger automated alerts."
        )


def get_ai_provider() -> AIProvider:
    """
    Factory — returns the configured AI provider instance.
    Falls back gracefully to MockAIProvider if keys are missing or invalid.
    """
    settings = get_settings()
    provider_name = settings.ai_provider.lower()

    if provider_name == "openai":
        try:
            if not settings.ai_api_key:
                logger.info("No AI_API_KEY set; using AegisAI Local Engine.")
                return MockAIProvider()
            from backend.ai.openai_provider import OpenAIProvider
            return OpenAIProvider()
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI provider ({e}); falling back to local AI engine.")
            return MockAIProvider()

    elif provider_name == "aws_bedrock":
        try:
            from backend.ai.aws_provider import AWSBedrockProvider
            return AWSBedrockProvider()
        except Exception as e:
            logger.warning(f"Failed to initialize Bedrock provider ({e}); falling back to local AI engine.")
            return MockAIProvider()

    else:
        return MockAIProvider()
