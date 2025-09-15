
import os

from typing import Optional, List, Dict
from logging import Logger, Formatter

from src.config.settings import get_settings, Settings
from src.utils.json import load_json
from src.log.base_logger import BaseLogger
from src.log.formatters import StandardUserFormatter
from src.log.filters import UserLogFilter, UserExclusionFilter

class UserLogger(BaseLogger):
    """
    Logger for a specific user's interactions.

    This logger is designed to track user-specific events, such as messages and
    commands. It uses a custom file path structure and applies specific filters.

    Configuration details:
      - Log file path: `<user_log_dir>/<user_id>/<user_id>.log`
      - Formatter: `StandardUserFormatter`
      - Filters: `UserLogFilter` and `UserExclusionFilter`
    """
    def __init__(self, user_id: str, user_name: str, settings: Optional[Settings] = None):
        """
        Initializes the UserLogger instance.

        Args:
            user_id (str): The unique identifier of the user.
            user_name (str): The name of the user.
            settings (Optional[Settings]): Application settings object.
        """
        self.user_id = user_id
        self.user_name = user_name
        self.excluded_users = self._load_excluded_users(settings)

        super().__init__(f"user_logs.{user_id}", settings)

    def _get_log_file_path(self) -> Optional[str]:
        """
        Returns the log file path for the specific user.

        The path is created based on the user's ID within the configured
        `user_log_dir`.

        Returns:
            Optional[str]: The path to the user's log file.
        """
        settings: Settings = self.settings
        base_dir = getattr(settings, "user_log_dir", os.path.join(os.getcwd(), "logs", "user_logs"))
        user_dir = os.path.join(base_dir, self.user_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, ".log")

    def _get_formatter(self):
        """
        Overrides the base method to use a custom formatter.

        Returns:
            StandardUserFormatter: An instance of the custom user formatter.
        """
        return StandardUserFormatter()

    def _get_filters(self):
        """
        Returns a list of filters for user logging.

        This method injects the user's context and applies an exclusion
        filter to prevent logging for specific users.

        Returns:
            list: A list containing `UserLogFilter` and `UserExclusionFilter`.
        """
        return [
            UserLogFilter(self.user_id, self.user_name),
            UserExclusionFilter(self.excluded_users),
        ]
    
    def _get_log_level(self) -> str:
        """
        Returns the log level for the user logger.

        Returns:
            str: The configured log level.
        """
        return getattr(self.settings, "user_log_level", "INFO")

    def _get_log_format(self) -> str:
        """
        Returns the log format.

        This logger is hardcoded to use the "standard" format.

        Returns:
            str: The string "standard".
        """
        return "standard"

    def _get_file_enabled(self) -> bool:
        """
        Returns whether file logging is enabled for the user logger.

        Returns:
            bool: True if file logging is enabled, False otherwise.
        """
        return getattr(self.settings, "user_log_file_enabled", True)

    def _get_console_enabled(self) -> bool:
        """
        Overrides the base method to disable console logging for user logs.

        Returns:
            bool: Always False to prevent console output.
        """
        return False
    
    def _get_retention_days(self) -> int:
        """
        Returns the log file retention period in days.

        Returns:
            int: The number of days for log retention.
        """
        return getattr(self.settings, "user_log_retention_days", 7)
    
    def _get_formatter_override(self) -> Optional[Formatter]:
        """
        Overrides the base method to use a custom formatter.

        Returns:
            Optional[Formatter]: A `StandardUserFormatter` instance.
        """
        return StandardUserFormatter()

    @staticmethod
    def _load_excluded_users(settings: Optional[Settings]) -> List[str]:
        """
        Loads the list of excluded user IDs from a JSON file.

        Args:
            settings (Optional[Settings]): The application settings object.

        Returns:
            List[str]: A list of user IDs to be excluded from logging.
        """
        settings = settings or get_settings()
        try:
            excluded_file: Dict = load_json(settings.excluded_users_path)
            raw_list: List[str] = excluded_file.get("excluded_users", [])
            return [uid.split(":", 1)[-1] for uid in raw_list]
        except Exception:
            return []

def get_user_logger(user_id: str, user_name: str) -> Logger:
    """
    Convenience function to get a UserLogger instance.

    Args:
        user_id (str): The unique identifier of the user.
        user_name (str): The name of the user.

    Returns:
        Logger: A configured UserLogger instance.
    """
    return UserLogger(user_id, user_name).get_logger()
