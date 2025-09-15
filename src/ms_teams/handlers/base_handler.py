from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from botbuilder.core import TurnContext

class BaseHandler(ABC):
    """
    Represents a foundational component for handling messages within a system.

    This class serves as an abstract base class, defining a consistent
    interface that all message handlers must implement. It is designed to
    be easily extensible for different conversational AI frameworks.

    Features:
        - Abstract interface for message handling logic.
        - Common methods for message and user information retrieval.
        - Built-in handler state management (enable/disable).
        - Extensible pre- and post-processing hooks.

    Attributes:
        name (str): The unique identifier or name of the handler.
        prefix (str): The command prefix used to trigger this handler.
        description (str): A brief description of the handler's purpose.
        enabled (bool): A flag indicating whether the handler is active.
    """
    
    def __init__(self, name: str, prefix: str, description: str = ""):
        """
        Initializes a new instance of the BaseHandler.

        Args:
            name (str): The unique identifier of the handler.
            prefix (str): The command prefix for the handler.
            description (str, optional): A brief description of the handler.
                                        Defaults to an empty string.
        """
        self.name: str = name
        self.prefix: str = prefix
        self.description: str = description
        self.enabled: bool = True
    
    @abstractmethod
    async def handle_message(self, turn_context: TurnContext) -> Optional[str]:
        """
        Handles an incoming message and generates a response.

        This is an abstract method that must be implemented by all subclasses.
        It contains the core logic for processing a user's message.

        Args:
            turn_context (TurnContext): The Bot Framework turn context containing
                                        the incoming message and conversation state.

        Returns:
            Optional[str]: The response message to be sent back to the user,
                        or `None` if no response is generated.
        """
        pass
    
    @abstractmethod
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """
        Determines if the handler is capable of processing a given message.

        This is an abstract method that must be implemented by subclasses to
        define the conditions under which they should be invoked.

        Args:
            message (str): The user's message text.
            context (Dict[str, Any], optional): Additional contextual information
                                                to aid in the determination. Defaults to None.

        Returns:
            bool: `True` if the handler can process the message, otherwise `False`.
        """
        pass

    @abstractmethod
    def get_help(self) -> Dict[str, Any]:
        """
        Abstract method to be implemented by subclasses to provide detailed help information.

        Returns:
            Dict[str, Any]: A dictionary containing structured help information.
        """
        pass
    
    @staticmethod 
    def _get_user_message(turn_context: TurnContext) -> str:
        """
        Retrieves the user's message text from the turn context.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The user's message text.
        """
        user_message = turn_context.activity.text
        return user_message
    
    @staticmethod 
    def _get_user_info(turn_context: TurnContext) -> str:
        """
        Retrieves the user's ID and name from the turn context.

        This is a static method for easily accessing user identity details.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            Tuple[str, str]: A tuple containing the user's ID and user's name.
        """
        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name
        return user_id, user_name
    
    def get_info(self) -> Dict[str, Any]:
        """
        Retrieves metadata about the handler.

        This method returns a dictionary containing the handler's name,
        description, enabled status, and class type.

        Returns:
            Dict[str, Any]: A dictionary containing handler metadata.
        """
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "type": self.__class__.__name__
        }
    
    def enable(self):
        """
        Activates the handler, allowing it to process messages.
        """
        self.enabled = True
    
    def disable(self):
        """
        Deactivates the handler, preventing it from processing messages.
        """
        self.enabled = False
    
    async def _pre_process(self, message: str, turn_context: TurnContext) -> str:
        """
        Pre-processes the incoming message before the core handling logic is executed.

        This method can be overridden by subclasses to implement custom
        pre-processing steps, such as normalization or cleaning.

        Args:
            message (str): The original user message.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The processed message.
        """
        return message.strip()
    
    async def _post_process(self, response: str, original_message: str, turn_context: TurnContext) -> str:
        """
        Post-processes the handler's response before it is sent to the user.

        This method can be overridden by subclasses to perform custom
        post-processing, such as formatting or adding supplementary information.

        Args:
            response (str): The response generated by the handler.
            original_message (str): The original user message.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The processed response.
        """
        return response