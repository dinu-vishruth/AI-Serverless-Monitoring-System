"""Groq provider using its OpenAI-compatible chat completions API."""

from backend.ai.openai_provider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """Groq-hosted LLM provider."""

    provider_id = "groq"
    provider_label = "Groq"
    api_key_setting = "groq_api_key"
    model_setting = "groq_model"
    api_base_url = "https://api.groq.com/openai/v1"
