import os
from typing import Optional
from logging import Logger

from src.config.settings import Settings
from src.log.base_logger import BaseLogger


class SystemLogger(BaseLogger):
    """
    Central logger for system-wide events.

    This class inherits from BaseLogger and configures a dedicated logger
    for system diagnostics and events.

    Configuration details:
      - Log file is located in the system logs folder.
      - Log format (JSON or standard) is based on application settings.
      - No additional filters are applied.
    """

    def __init__(self, name: str = "system", settings: Optional[Settings] = None):
        """
        Initializes the SystemLogger.

        Args:
            name (str): The name of the logger instance. Defaults to "system".
            settings (Optional[Settings]): Application settings object.
        """
        super().__init__(name, settings)

    def _get_log_file_path(self) -> Optional[str]:
        """
        Returns the file path for the system log.

        The path is determined by the `sys_log_file` setting or a default
        fallback path if not specified.

        Returns:
            Optional[str]: The path to the system log file.
        """
        settings: Settings = self.settings
        log_file = getattr(settings, "sys_log_file", None)
        if not log_file:
            # fallback por si no existe en settings
            base_dir = os.path.join(os.getcwd(), "logs", "sys_logs")
            os.makedirs(base_dir, exist_ok=True)
            log_file = os.path.join(base_dir, "mst_bot.log")
        return log_file

    def _get_filters(self):
        """
        Returns the filters for the logger.

        SystemLogger does not require any additional filters.

        Returns:
            list: An empty list.
        """
        return []
    
    def _get_log_level(self) -> str:
        """
        Returns the log level from settings or a default value.

        Returns:
            str: The configured log level.
        """
        return getattr(self.settings, "sys_log_level", "INFO")

    def _get_log_format(self) -> str:
        """
        Returns the log format from settings or a default value.

        Returns:
            str: The configured log format ("json" or "standard").
        """
        return getattr(self.settings, "sys_log_format", "standard")

    def _get_file_enabled(self) -> bool:
        """
        Returns whether file logging is enabled for the system logger.

        Returns:
            bool: True if file logging is enabled, False otherwise.
        """
        return getattr(self.settings, "sys_log_file_enabled", True)

    def _get_retention_days(self) -> int:
        """
        Returns the log file retention period in days.

        Returns:
            int: The number of days to retain log files.
        """
        return getattr(self.settings, "sys_log_retention_days", 7)

def get_system_logger(name: str = "system") -> Logger:
    """
    Convenience function to get a SystemLogger instance.

    Args:
        name (str): The name for the logger.

    Returns:
        Logger: A configured SystemLogger instance.
    """
    return SystemLogger(name).get_logger()
