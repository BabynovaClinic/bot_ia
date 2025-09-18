from typing import Optional
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

from src.utils.yaml import load_yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DOTENV_PATH = BASE_DIR / ".env"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

# Ruta del secret file en Render
SECRET_USERS_PATH = Path("/etc/secrets/user_data.json")

SENSITIVE_KEYS = {
    "default_admin_user_id",
    "app_id",
    "app_password",
    "app_tenant",
    "site_url",
    "site_id",
    "site_id_ref",
    "drive_id",
    "folder_id",
    "openai_api_key",
    "openai_vector_store_id_sgc",
    "openai_vector_store_id_ref",
}


class Settings(BaseSettings):
    """
    Main application settings, loading from environment variables and .env file.
    """

    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Server Configuration ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=3978)

    # --- Default Admin Configuration ---
    default_admin_user_id: str
    default_admin_name: str = Field(default="Administrador")
    default_admin_email: str = Field(default="admin@babynovaclinic.com")

    # --- Files Configuration ---
    # Si existe el secret file en Render, usarlo, si no, usar local
    users_path: str = Field(
        default=str(SECRET_USERS_PATH) if SECRET_USERS_PATH.exists() else "./data/user_data.json"
    )
    excluded_users_path: str = Field(default="./data/excluded_user_data.json")
    doc_sync_path: str = Field(default="./data/doc_sync_data.json")
    ref_sync_path: str = Field(default="./data/ref_sync_data.json")
    doc_meta_path: str = Field(default="./data/doc_meta_data.json")
    ref_meta_path: str = Field(default="./data/ref_meta_data.json")

    # --- Stats Configuration ---
    stats_file_path: str = Field(default="./data/stats/usage_stats.csv")

    # --- Templates Configuration ---
    templates_dir: str = Field(default="./config/templates")

    # --- LibreOffice Configuration ---
    libreoffice_path: str = Field(default="C:/Program Files/LibreOffice/program/soffice.exe")

    # --- Application Configuration ---
    app_id: str
    app_password: str
    app_tenant: str

    # --- Share Point Configuration ---
    site_url: str
    site_id: str
    drive_id_sgc: str
    drive_id_ref: str
    folder_id: str
    file_extensions: Optional[list[str]] = Field(default=["pdf", "doc", "docx"])
    whitelist_paths: Optional[list[str]] = Field(default=[])
    blacklist_paths: Optional[list[str]] = Field(default=[])
    keywords_to_skip: Optional[list[str]] = Field(default=["obsoleto", "obsoletos"])

    # --- Synchronization Configuration ---
    sync_hour: int = Field(default=3)
    sync_min: int = Field(default=0)

    # --- Handler Configuration ---
    handler_cfg_path: str = Field(default="./config/handler_config.yaml")

    # --- OpenAI API Configuration ---
    openai_api_key: str
    openai_vector_store_id_sgc: str
    openai_vector_store_id_ref: str

    # --- Large Language Model Configuration ---
    openai_model_name: str = Field(default="gpt-3.5-turbo")
    openai_emb_name: str = Field(default="text-embedding-3-small")

    llm_max_input_tokens: int = Field(default=4000)
    llm_max_output_tokens: int = Field(default=1000)
    llm_temperature: float = Field(default=0.2)
    llm_top_p: float = Field(default=1.0)

    llm_n_responses: int = Field(default=1)
    llm_presence_penalty: float = Field(default=0.0)
    llm_frequency_penalty: float = Field(default=0.5)

    # --- Logger Configuration ---
    sys_log_level: str = Field(default="WARNING")
    sys_log_format: str = Field(default="standard")
    sys_log_file: str = Field(default="./logs/sys_logs/mst_bot.log")
    sys_log_file_enabled: bool = Field(default=True)
    sys_log_retention_days: int = Field(default=30)

    user_log_level: str = Field(default="INFO")
    user_log_dir: str = Field(default="./logs/user_logs/")
    user_log_retention_days: int = Field(default=30)
    user_log_file_enabled: bool = Field(default=True)

    def get_base_url(self) -> str:
        """Get the base URL for the application."""
        protocol = "https"
        return f"{protocol}://{self.host}:{self.port}"

    def validate_llm_keys(self) -> bool:
        """Validate that required LLM configuration is present."""
        if not self.openai_api_key:
            print("WARNING: OPENAI_API_KEY is not set.")
            return False
        return True


# Global settings instance (singleton pattern)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern)."""
    global _settings
    if _settings is None:
        config_dict = {}
        if CONFIG_PATH.exists():
            config_dict = load_yaml(str(CONFIG_PATH))
        else:
            raise FileNotFoundError(f"ERROR: File not found {CONFIG_PATH}")

        # Remove sensitive keys
        keys_to_remove = [key for key in config_dict.keys() if key.lower() in SENSITIVE_KEYS]
        for key in keys_to_remove:
            del config_dict[key]

        try:
            _settings = Settings(**config_dict)
        except ValidationError as e:
            raise ValidationError(f"ERROR: Validation failed in configuration: {e}")

    return _settings
