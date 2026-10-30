"""
AWS Bedrock provider implementation.
"""

import json
import boto3
from backend.ai.provider import AIProvider, AIProviderError
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AWSBedrockProvider(AIProvider):
    """AWS Bedrock provider (Claude, Titan, etc.)."""

    def __init__(self):
        settings = get_settings()
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.bedrock_region,
        )
        self.model_id = settings.bedrock_model_id
        self.provider_name = f"AWS Bedrock ({self.model_id})"

    async def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """Sends an analysis request to Bedrock and parses the JSON response."""
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt},
                ],
            })

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "")

            if not content:
                raise AIProviderError(
                    "Empty response from Bedrock",
                    provider="aws_bedrock",
                )

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON
                import re
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                raise AIProviderError(
                    "Could not parse Bedrock response as JSON",
                    provider="aws_bedrock",
                )

        except AIProviderError:
            raise
        except Exception as e:
            logger.error(f"Bedrock API error: {e}", extra={"action": "ai_analyze"})
            raise AIProviderError(
                f"Bedrock API call failed: {str(e)}",
                provider="aws_bedrock",
                recoverable=True,
            )

    async def chat(self, messages: list[dict]) -> str:
        """Sends a chat conversation to Bedrock."""
        try:
            # Convert messages format for Claude
            system_msg = ""
            chat_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    chat_messages.append(msg)

            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "temperature": 0.4,
                "system": system_msg,
                "messages": chat_messages,
            })

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body.get("content", [{}])[0].get("text", "")

        except Exception as e:
            logger.error(f"Bedrock chat error: {e}", extra={"action": "ai_chat"})
            raise AIProviderError(
                f"Bedrock chat failed: {str(e)}",
                provider="aws_bedrock",
                recoverable=True,
            )
