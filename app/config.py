from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    # Kubernetes settings
    kubernetes_enabled: bool = False
    kubernetes_kubeconfig_path: str | None = None
    kubernetes_namespace: str = "default"
    kubernetes_use_local_fixtures: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
