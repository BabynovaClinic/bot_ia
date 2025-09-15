from typing import Dict
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

class MemoryManager:
    """
    Centralized manager for user conversation history.

    This class provides a single point of access for retrieving and managing
    conversation history instances for each user, ensuring that conversation
    history can be shared across different handler types (e.g., LLMHandler,
    RAGHandler). It uses a dictionary to store a dedicated history instance
    for each user, indexed by their unique user ID.

    Attributes:
        _user_histories (Dict[str, BaseChatMessageHistory]): A dictionary that
            maps a user's unique ID to their conversation history instance.
    """
    def __init__(self):
        """
        Initializes a new instance of the MemoryManager.
        """
        self._user_histories: Dict[str, BaseChatMessageHistory] = {}

    def get_history_for_user(self, user_id: str) -> BaseChatMessageHistory:
        """
        Retrieves or creates a conversation history instance for a specific user.

        If a history instance for the given user ID already exists, it is
        returned. Otherwise, a new ChatMessageHistory instance is created, stored,
        and then returned.

        Args:
            user_id (str): The unique identifier of the user.

        Returns:
            BaseChatMessageHistory: The history instance associated with the user.
        """
        if user_id not in self._user_histories:
            self._user_histories[user_id] = ChatMessageHistory()
        return self._user_histories[user_id]
    
    def clear_history_for_user(self, user_id: str) -> None:
        """
        Clears the conversation history for a specific user.

        Args:
            user_id (str): The unique identifier of the user.
        """
        history = self._user_histories.get(user_id)
        if history:
            try:
                history.clear()
            except Exception:
                self._user_histories[user_id] = ChatMessageHistory()