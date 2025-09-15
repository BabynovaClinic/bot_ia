
import os
import sys
import logging

from abc import ABC, abstractmethod
from typing import Optional, List
from logging import Formatter, Logger, Filter

from src.config.settings import get_settings, Settings
from src.log.file_handlers import SafeTimedRotatingFileHandler
from src.log.formatters import JSONFormatter, StandardFormatter

class BaseLogger(ABC):
    """
    Base class that centralizes the creation and configuration of loggers.

    This class provides a common structure for all loggers in the application.
    It prevents the duplication of handlers and uses a template method pattern
    for subclasses to define the log file path, filters, and other
    configuration settings.

    Attributes:
        name (str): The name of the logger instance.
        settings (Settings): The application's settings object.
        logger (Logger): The configured logging.Logger instance.
    """
    def __init__(self, name: str, settings: Optional[Settings] = None):
        """
        Initializes the BaseLogger instance.

        Args:
            name (str): The name to be used for the logger.
            settings (Optional[Settings]): Application settings object. If None,
                                           it will be retrieved from a global
                                           singleton.
        """
        self.name = name
        self.settings: Settings = settings or get_settings()
        self.logger: Logger = logging.getLogger(self.name)

        if not self.logger.handlers:
            self._configure_logger()

    def get_logger(self) -> Logger:
        """
        Returns the configured logging.Logger instance.

        Returns:
            Logger: The configured logger object.
        """
        return self.logger

    def _configure_logger(self):
        """
        Configures the logger with handlers, formatters, and filters.

        This method sets the log level, adds console and file handlers based on
        the subclass's configuration, and applies any defined filters.
        It prevents handlers from being added multiple times.
        """
        # Nivel
        log_level_str = self._get_log_level()
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # Formatter
        fmt = self._get_log_format()
        if fmt.lower() == "json":
            formatter = JSONFormatter()
        else:
            formatter = self._get_formatter_override() or StandardFormatter()

        # Console handler (por defecto True si no se sobrescribe)
        if self._get_console_enabled():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if self._get_file_enabled():
            log_file_path = self._get_log_file_path()
            if log_file_path:
                os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
                file_handler = SafeTimedRotatingFileHandler(
                    filename=log_file_path,
                    when='midnight',
                    interval=1,
                    backupCount=self._get_retention_days(),
                    encoding='utf-8',
                )
                file_handler.setLevel(log_level)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

        # Filtros
        for f in self._get_filters():
            self.logger.addFilter(f)

        self.logger.propagate = False

    @abstractmethod
    def _get_log_file_path(self) -> Optional[str]:
        """
        Abstract method to be implemented by subclasses.

        This method should return the specific file path for the log file.

        Returns:
            Optional[str]: The path to the log file.
        """
        pass

    @abstractmethod
    def _get_log_level(self) -> str:
        """
        Abstract method to be implemented by subclasses.

        This method should return the desired logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").

        Returns:
            str: The logging level as a string.
        """
        pass

    @abstractmethod
    def _get_log_format(self) -> str:
        """
        Abstract method to be implemented by subclasses.

        This method should return the desired log format ("json" or "standard").

        Returns:
            str: The log format as a string.
        """
        pass

    @abstractmethod
    def _get_file_enabled(self) -> bool:
        """
        Abstract method to be implemented by subclasses.

        This method should return whether file logging is enabled.

        Returns:
            bool: True if file logging is enabled, False otherwise.
        """
        pass

    @abstractmethod
    def _get_retention_days(self) -> int:
        """
        Abstract method to be implemented by subclasses.

        This method should return the number of days to retain log files.

        Returns:
            int: The number of days for log retention.
        """
        pass

    # === Hooks opcionales ===

    def _get_filters(self) -> List[Filter]:
        """
        Optional hook for subclasses to add specific filters.

        Returns:
            List[logging.Filter]: A list of logging filter objects.
        """
        return []

    def _get_formatter_override(self) -> Optional[Formatter]:
        """
        Optional hook for subclasses to provide a custom formatter.

        Returns:
            Optional[Formatter]: A custom Formatter instance, or None to use
                                 the default StandardFormatter.
        """
        return None

    def _get_console_enabled(self) -> bool:
        """
        Optional hook for subclasses to disable console logging.

        Returns:
            bool: True if console logging is enabled, False otherwise.
        """
        return True
