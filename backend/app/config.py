from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    openai_api_key: str = ""
    openrouter_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def missing_keys(self) -> list[str]:
        missing: list[str] = []
        if not self.openai_api_key.strip():
            missing.append("OPENAI_API_KEY")
        if not self.openrouter_api_key.strip():
            missing.append("OPENROUTER_API_KEY")
        return missing


def get_settings() -> Settings:
    return Settings()
