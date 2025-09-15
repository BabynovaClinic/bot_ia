from typing import Optional
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

from src.utils.yaml import load_yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DOTENV_PATH = BASE_DIR / ".env"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

SENSITIVE_KEYS = {
    "default_admin_user_id",
    "app_id",
    "app_password",
    "app_tenant",
    "site_url",
    "site_id",
    "site_id_ref"
    "drive_id",
    "folder_id",
    "openai_api_key",
    "openai_vector_store_id_sgc"
    "openai_vector_store_id_ref"
}

class Settings(BaseSettings):
    """
    Main application settings, loading from environment variables and .env file.

    This class manages all application configurations, including server, file paths, LibreOffice,
    SharePoint, OpenAI API, LLM, and logger settings. It uses Pydantic's BaseSettings to load
    values from environment variables and a .env file, ensuring a centralized and type-safe
    configuration.

    Features:
        - Centralized configuration management.
        - Loads settings from .env file and environment variables.
        - Type validation for all configuration fields.
        - Provides methods for validating specific configuration groups and retrieving a base URL.

    Attributes:
        host (str): The host address for the server.
        port (int): The port for the server.
        default_admin_user_id (str): The ID of the default administrator user.
        default_admin_name (str): The name of the default administrator.
        default_admin_email (str): The email of the default administrator.
        users_path (str): Path to the users data file.
        excluded_users_path (str): Path to the excluded users data file.
        doc_sync_path (str): Path to the document synchronization data file.
        ref_sync_path (str): Path to the reference synchronization data file.
        doc_meta_path (str): Path to the document metadata file.
        ref_meta_path (str): Path to the reference metadata file.
        stats_file_path (str): Path to the statistics .csv file.
        templates_dir (str): Path to the templates directory.
        libreoffice_path (str): Path to the LibreOffice executable.
        app_id (str): The application ID for authentication.
        app_password (str): The application password.
        app_tenant (str): The application tenant ID.
        site_url (str): The URL of the SharePoint site.
        site_id (str): The ID of the SharePoint site.
        drive_id_sgc (str): The drive ID for the SGC (Sistema de Gestión de Calidad) documents.
        drive_id_ref (str): The drive ID for the reference documents.
        folder_id (str): The folder ID within the SharePoint drive.
        file_extensions (Optional[list[str]]): List of allowed file extensions.
        whitelist_paths (Optional[list[str]]): List of SharePoint paths to include for synchronization.
        blacklist_paths (Optional[list[str]]): List of SharePoint paths to exclude from synchronization.
        keywords_to_skip (Optional[list[str]]): List of keywords to skip in file or folder names.
        openai_api_key (str): The API key for OpenAI services.
        openai_vector_store_id_sgc (str): The ID of the vector store for SGC documents.
        openai_vector_store_id_ref (str): The ID of the vector store for reference documents.
        openai_model_name (str): The name of the OpenAI model to use.
        openai_emb_name (str): The name of the embedding model.
        llm_directives_file (str): Path to the file containing LLM directives.
        llm_max_input_tokens (int): Maximum number of input tokens for the LLM.
        llm_max_output_tokens (int): Maximum number of output tokens for the LLM.
        llm_temperature (float): The temperature for LLM text generation.
        llm_top_p (float): The top-p value for LLM text generation.
        llm_n_responses (int): The number of responses to generate.
        llm_presence_penalty (float): The presence penalty for the LLM.
        llm_frequency_penalty (float): The frequency penalty for the LLM.
        sys_log_level (str): The logging level for the main application logs.
        sys_log_format (str): The format of the log messages.
        sys_log_file (str): Path to the main log file.
        sys_log_file_enabled (bool): Flag to enable/disable main log file.
        sys_log_retention_days (int): Number of days to retain main log files.
        user_log_level (str): The logging level for user-specific logs.
        user_log_dir (str): Directory for user-specific logs.
        user_log_retention_days (int): Number of days to retain user-specific logs.
        user_log_file_enabled (bool): Flag to enable/disable user log files.
    """

    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # --- Server Configuration ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=3978)

    # --- Default Admin Configuration ---
    default_admin_user_id: str
    default_admin_name: str = Field(default="Administrador")
    default_admin_email: str = Field(default="admin@babynovaclinic.com") 

    # --- Files Configuration ---
    users_path: str = Field(default="./data/user_data.json")
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

    # --- Share Point Configuration
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
        """
        Get the base URL for the application.

        Returns:
            str: The constructed base URL (e.g., 'https://0.0.0.0:8000').
        """
        protocol = "https"
        return f"{protocol}://{self.host}:{self.port}"
    
    def validate_llm_keys(self) -> bool:
        """
        Validate that required LLM configuration is present.

        Returns:
            bool: True if the OpenAI API key is set, False otherwise.
        """
        if not self.openai_api_key:
            print("WARNING: OPENAI_API_KEY is not set.")
            return False
        return True

# Global settings instance (singleton pattern)
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """
    Get application settings (singleton pattern).

    This function ensures that only one instance of the Settings class is created.
    It first attempts to load settings from a `config.yaml` file, if it exists.
    Sensitive keys are removed from the loaded dictionary before creating the Settings object.

    Raises:
        FileNotFoundError: If the 'config.yaml' file is not found.
        ValidationError: If validation of the configuration fails.

    Returns:
        Settings: The singleton instance of the application settings.
    """
    global _settings
    if _settings is None:
        config_dict = {}
        if CONFIG_PATH.exists():
            config_dict = load_yaml(str(CONFIG_PATH))
        else:
            raise FileNotFoundError(f"ERROR: File not found {CONFIG_PATH}")

        keys_to_remove = []
        for key in config_dict.keys():
            if key.lower() in SENSITIVE_KEYS:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del config_dict[key]

        try:
            _settings = Settings(**config_dict)
        except ValidationError as e:
            raise ValidationError(f"ERROR: Validation failed in configuration: {e}")

    return _settings
