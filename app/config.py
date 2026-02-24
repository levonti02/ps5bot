from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    ADMIN_IDS: list[int] = []

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ps5bot:ps5bot@db:5432/ps5bot"

    # YooKassa
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = "https://t.me/your_bot"

    # Webhook / FastAPI
    WEBHOOK_HOST: str = "https://example.com"
    WEBHOOK_PATH: str = "/api/webhook/telegram"
    YOOKASSA_WEBHOOK_PATH: str = "/api/webhook/yookassa"
    FASTAPI_PORT: int = 8000

    # Tariffs: duration_minutes -> price in kopecks
    @property
    def tariffs(self) -> dict[int, int]:
        return {
            30: 30000,
            60: 55000,
            90: 85000,
            120: 110000,
        }

    # Session timings
    HOLD_TIMEOUT_MINUTES: int = 10
    ACTIVATION_WINDOW_MINUTES: int = 10
    BUFFER_BETWEEN_SLOTS_MINUTES: int = 5
    BOOKING_HORIZON_DAYS: int = 14

    # Shelly retry
    SHELLY_RETRY_COUNT: int = 3
    SHELLY_TIMEOUT_SECONDS: int = 5

    # Mock payment (skip YooKassa, instant confirmation)
    PAYMENT_MOCK: bool = True

    # Timezone
    TIMEZONE: str = "Europe/Moscow"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
