from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    market_data_provider: str = "twelve_data"
    twelve_data_api_key: str = ""
    twelve_data_symbols: str = "EUR/USD,GBP/USD,USD/JPY,AUD/USD,USD/CAD,EUR/GBP,AUD/NZD,XAU/USD,XAG/USD,BTC/USD"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_alerts_enabled: bool = True
    telegram_retry_attempts: int = 3
    telegram_retry_delay_seconds: float = 1.0
    alert_webhook_url: str = ""
    oanda_environment: str = "practice"
    oanda_practice_token: str = ""
    oanda_live_token: str = ""
    oanda_account_id: str = ""
    oanda_instruments: str = "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,EUR_GBP,AUD_NZD,XAU_USD,XAG_USD,BTC_USD"
    oanda_granularity: str = "H1"
    oanda_price_component: str = "MBA"
    data_dir: str = "./data"
    database_url: str = "sqlite:///./data/metadata.db"
    biquote_calendar_url: str = "https://biquote.io/api/calendar/upcoming"
    biquote_importance: str = "high"
    biquote_countries: str = "US,EU,GB,JP,AU,CA,NZ,CH"
    gdelt_doc_url: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    gdelt_query: str = "(forex OR currency OR central bank OR interest rate)"
    gdelt_lookback_minutes: int = 180
    live_trading: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        if self.oanda_environment not in {"practice", "live"}:
            raise ValueError("OANDA_ENVIRONMENT must be practice or live")
        if self.market_data_provider not in {"twelve_data", "oanda"}:
            raise ValueError("MARKET_DATA_PROVIDER must be twelve_data or oanda")
        if self.telegram_retry_attempts < 1 or self.telegram_retry_delay_seconds < 0:
            raise ValueError("Telegram retry settings are invalid")
        if self.live_trading:
            raise ValueError("Live order execution is not implemented in Phase 4")
