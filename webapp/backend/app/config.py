from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore")

    measures_dir: Path = Path("./data/measures")

    @property
    def measures_dir_resolved(self) -> Path:
        return self.measures_dir.resolve()


settings = Settings()
