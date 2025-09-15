
import json
from datetime import datetime
from typing import Any, Dict
from logging import LogRecord, Formatter

class JSONFormatter(Formatter):
    """
    Formats log records into a structured JSON format.

    This class extends `logging.Formatter` to serialize log entries as JSON objects,
    making them ideal for machine-readable logging and integration with log management systems.

    Features:
        - Serializes log records into a single-line JSON string.
        - Includes standard log fields such as `timestamp`, `level`, and `message`.
        - Automatically adds exception information when present.
        - Supports the inclusion of arbitrary extra fields for custom context.
    """

    def format(self, record: LogRecord) -> str:
        """
        Formats a log record as a JSON string.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log record as a JSON string.
        """
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry, ensure_ascii=False)

class StandardFormatter(Formatter):
    """
    Formats user log records into a readable text format.

    This class extends `logging.Formatter` to customize log messages by including
    the user's name and the message origin (BOT or USER).

    Features:
        - Adds user-specific context to log messages.
        - Ensures consistent log output format.

    Attributes:
        fmt (str): The format string for log messages.
        datefmt (str): The date format string.
    """
    def __init__(self):
        """
        Initializes the standard user formatter.
        """
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

class StandardUserFormatter(Formatter):
    """
    Formats user log records into a readable text format.

    This class extends `logging.Formatter` to customize log messages by including
    the user's name and the message origin (BOT or USER).

    Features:
        - Adds user-specific context to log messages.
        - Ensures consistent log output format.

    Attributes:
        fmt (str): The format string for log messages.
        datefmt (str): The date format string.
    """
    def __init__(self):
        """
        Initializes the standard user formatter.
        """
        super().__init__(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record: LogRecord) -> str:
        """
        Formats the log record by adding the user's name to the message.

        This method checks for the `user_name` attribute on the log record and
        prepends it to the log message, then calls the parent formatter.

        Args:
            record (logging.LogRecord): The log record instance to format.

        Returns:
            str: The formatted log message string.
        """
        if hasattr(record, 'user_name'):
            full_message = f"[{record.user_name}] - {record.msg}"
            record.msg = full_message

        return super().format(record)