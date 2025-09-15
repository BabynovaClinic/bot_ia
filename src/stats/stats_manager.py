import csv
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from src.log.system_logger import Logger, get_system_logger

class StatsManager:
    """
    Manages the collection and storage of usage statistics.

    This class provides a simple interface for logging various events related to
    application usage, such as command executions, message processing, and
    user interactions. It records this data to a CSV file, ensuring that
    metrics like timestamps, user IDs, event types, and durations are
    systematically captured for analysis.

    Features:
        - Automatic creation of the statistics file with headers if it doesn't exist.
        - Timestamping of all logged events.
        - Recording of key event details, including user information, handler name,
        command, duration, and status.
        - Centralized logging point to maintain consistent data format.

    Attributes:
        file_path (Path): The path to the CSV file where statistics are stored.
        system_logger (Logger): A logger for internal system events and diagnostics.
    """
    def __init__(self, file_path: str):
        """
        Initializes a new instance of the StatsManager.

        This constructor sets up the file path for the statistics CSV and ensures
        that the file exists, creating it with the necessary headers if it's not found.

        Args:
            file_path (str): The file path where the usage statistics will be stored.
        """
        self.file_path:Path = Path(file_path)
        self.system_logger: Logger = get_system_logger(__name__)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """
        Ensures that the statistics file exists.

        If the file does not exist, this method creates it and writes the
        column headers for the CSV file. It also ensures that the parent
        directory structure is in place.
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.file_path.exists():
            with open(self.file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "user_id", "user_name", "event_type", 
                    "handler", "command", "duration_ms", "status"
                ])

    def log(
        self,
        user_info: Dict[str, Any],
        event_type: str,
        handler_name: str,
        command: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: str = "success"
    ):
        """
        Logs a usage event to the statistics file.

        This method appends a new row to the CSV file with details about a
        specific event, such as a message being processed or a command being
        executed. It includes a timestamp and other relevant metrics.

        Args:
            user_info (Dict[str, Any]): A dictionary containing user-related
                                        information, typically with 'user_id'
                                        and 'name'.
            event_type (str): The type of event being logged (e.g., "llm_query",
                            "admin_command").
            handler_name (str): The name of the handler that processed the event.
            command (Optional[str]): The specific command executed, if applicable.
                                    Defaults to None.
            duration_ms (Optional[float]): The duration of the event in milliseconds.
                                        Defaults to None.
            status (str): The outcome of the event, either "success" or "error".
                        Defaults to "success".
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(self.file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, 
                    user_info.get("user_id", "unknown"),
                    user_info.get("name", "unknown"),
                    event_type,
                    handler_name,
                    command if command else "",
                    f"{duration_ms:.2f}" if duration_ms is not None else "",
                    status
                ])
        except Exception as e:
            self.system_logger.error(f"Error logging stats: {e}")