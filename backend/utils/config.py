"""
Configuration module — loads settings from environment variables.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS
    aws_region: str = Field(default="ap-south-2", alias="AWS_REGION")

    # DynamoDB Tables
    monitoring_table: str = Field(default="MonitoringData", alias="MONITORING_TABLE")
    ai_analysis_table: str = Field(default="AIAnalysis", alias="AI_ANALYSIS_TABLE")
    incident_table: str = Field(default="Incidents", alias="INCIDENT_TABLE")
    services_table: str = Field(default="Services", alias="SERVICES_TABLE")

    # AI Provider
    ai_provider: str = Field(default="groq", alias="AI_PROVIDER")
    ai_api_key: Optional[str] = Field(default=None, alias="AI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")

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
    local_monitoring_enabled: bool = Field(default=True, alias="LOCAL_MONITORING_ENABLED")
    api_base_url: str = Field(default="http://127.0.0.1:8001", alias="API_BASE_URL")
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
    ml_anomaly_threshold: float = Field(default=0.5, ge=0, le=1, alias="ML_ANOMALY_THRESHOLD")
    model_bucket: Optional[str] = Field(default=None, alias="MODEL_BUCKET")
    admin_token: Optional[str] = Field(default=None, alias="ADMIN_TOKEN")
    admin_secret_arn: Optional[str] = Field(default=None, alias="ADMIN_SECRET_ARN")
    groq_secret_arn: Optional[str] = Field(default=None, alias="GROQ_SECRET_ARN")
    demo_enabled: bool = Field(default=False, alias="DEMO_ENABLED")
    allow_private_targets: bool = Field(default=False, alias="ALLOW_PRIVATE_TARGETS")
    telemetry_retention_days: int = Field(default=30, ge=1, le=365, alias="TELEMETRY_RETENTION_DAYS")
    failure_threshold: int = Field(default=3, ge=1, le=20, alias="FAILURE_THRESHOLD")
    recovery_threshold: int = Field(default=2, ge=1, le=20, alias="RECOVERY_THRESHOLD")
    escalation_seconds: int = Field(default=900, ge=60, alias="ESCALATION_SECONDS")

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

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", env_ignore_empty=True, populate_by_name=True)


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Returns the cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
