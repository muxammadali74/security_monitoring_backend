from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "My Microservice"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASS: str = "secret_password"
    DB_NAME: str = "my_service_db"

    JWT_SECRET_KEY: str = "SUPER_SECRET_KEY_FOR_JWT_SIGNING_DO_NOT_SHARE_IT"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    ADMIN_REGISTRATION_SECRET: str = "super_secret_key_123"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
