
import logging
from logging import Filter

class UserExclusionFilter(Filter):
    """
    A filter to exclude specific users from being logged.

    This filter is applied to a logger to prevent log records from being processed
    if their associated user ID is found in a predefined list of excluded users.

    Features:
        - Filters logs based on user ID.
        - Provides a mechanism for privacy and selective logging.

    Attributes:
        excluded_users (list): A list of user IDs to be excluded from logging.
    """
    def __init__(self, excluded_users: list):
        """
        Initializes the user exclusion filter with a list of users to exclude.

        Args:
            excluded_users (list): A list of user IDs to exclude.
        """
        super().__init__()
        self.excluded_users = excluded_users

    def filter(self, record) -> bool:
        """
        Determines whether the log record should be processed.

        This method returns `False` if the `user_id` attribute of the log record
        is in the list of excluded users, effectively dropping the log message.

        Args:
            record (logging.LogRecord): The log record instance to filter.

        Returns:
            bool: `True` if the record should be logged, `False` otherwise.
        """
        if hasattr(record, 'user_id') and record.user_id in self.excluded_users:
            return False
        return True

class UserLogFilter(Filter):
    """
    A filter to add user context to log records.

    This filter is responsible for injecting the user's ID and name into
    each log record, making the information available to formatters.

    Features:
        - Enriches log records with user-specific data.
        - Connects log messages to a specific user session.

    Attributes:
        user_id (str): The unique ID of the user.
        user_name (str): The readable name of the user.
    """
    def __init__(self, user_id: str, user_name: str):
        """
        Initializes the user context filter with user-specific data.

        Args:
            user_id (str): The unique ID of the user.
            user_name (str): The readable name of the user.
        """
        super().__init__()
        self.user_id = user_id
        self.user_name = user_name

    def filter(self, record) -> bool:
        """
        Injects the user's ID and name into the log record.

        This method adds `user_id` and `user_name` attributes to the log record
        and then returns `True` to allow the record to be processed.

        Args:
            record (logging.LogRecord): The log record instance to modify.

        Returns:
            bool: `True` to allow the record to be logged.
        """
        record.user_id = self.user_id
        record.user_name = self.user_name
        return True