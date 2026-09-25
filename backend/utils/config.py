"""
Configuration module — loads settings from environment variables.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")

    # DynamoDB Tables
    monitoring_table: str = Field(default="MonitoringData", alias="MONITORING_TABLE")
    ai_analysis_table: str = Field(default="AIAnalysis", alias="AI_ANALYSIS_TABLE")
    incident_table: str = Field(default="Incidents", alias="INCIDENT_TABLE")
    services_table: str = Field(default="Services", alias="SERVICES_TABLE")

    # AI Provider
    ai_provider: str = Field(default="openai", alias="AI_PROVIDER")
    ai_api_key: Optional[str] = Field(default=None, alias="AI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")

    # AWS Bedrock
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        alias="BEDROCK_MODEL_ID",
    )
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")

    # SNS
    sns_topic_arn: Optional[str] = Field(default=None, alias="SNS_TOPIC_ARN")
    sns_alert_enabled: bool = Field(default=True, alias="SNS_ALERT_ENABLED")

    # API & Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")
    api_stage: str = Field(default="dev", alias="API_STAGE")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS"
    )

    # ML
    ml_model_type: str = Field(default="isolation_forest", alias="ML_MODEL_TYPE")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ML
    ml_model_path: str = Field(default="ml-models/", alias="ML_MODEL_PATH")
    ml_retrain_threshold: int = Field(default=100, alias="ML_RETRAIN_THRESHOLD")
    ml_contamination: float = Field(default=0.1, alias="ML_CONTAMINATION")

    # Security
    jwt_secret_key: str = Field(default="dev-secret-change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(default=60, alias="JWT_EXPIRATION_MINUTES")

    # CloudWatch
    cloudwatch_log_group: str = Field(
        default="/aws/lambda/health-checker", alias="CLOUDWATCH_LOG_GROUP"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Returns the cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
