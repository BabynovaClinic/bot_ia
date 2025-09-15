
from typing import Dict, List, Optional, Any
from src.ms_teams.handlers.base_handler import BaseHandler

from src.log.system_logger import Logger, get_system_logger

class HandlerRegistry:
    """
    Manages a centralized registry for message handlers.

    This class provides a robust system for registering, retrieving, and managing the lifecycle of message handlers.
    It ensures that messages can be dynamically routed to the correct handler based on configuration.

    Features:
        - Centralized handler registration and unregistration
        - Dynamic management of a default handler
        - Lifecycle control (enabling/disabling) for individual handlers
        - Retrieval of handler information and status

    Attributes:
        handlers (Dict[str, BaseHandler]): A dictionary mapping unique handler names to their instances.
        default_handler (Optional[str]): The name of the currently designated default handler.
        logger: An instance of a logger for class-specific logging.
    """

    def __init__(self):
        """
        Initializes the HandlerRegistry with an empty handler dictionary.
        """
        self.handlers: Dict[str, BaseHandler] = {}
        self.default_handler: Optional[str] = None
        self.system_logger = get_system_logger(__name__)

    def register_handler(self, name: str, handler: BaseHandler, is_default: bool = False) -> None:
        """
        Registers a new message handler in the registry.

        This method adds a handler instance to the registry, associating it with a unique name.
        It can also set the registered handler as the default handler.

        Args:
            name (str): A unique name or identifier for the handler.
            handler (BaseHandler): An instance of the handler to be registered.
            is_default (bool, optional): If True, sets this handler as the default. Defaults to False.
        """     
        if not isinstance(handler, BaseHandler):
            raise ValueError(f"Handler must inherit from BaseHandler")
        
        if name in self.handlers:
            self.system_logger.warning(f"Handler '{name}' already exists, replacing...")
        
        self.handlers[name] = handler
        
        if is_default or not self.default_handler:
            self.default_handler = name
            self.system_logger.info(f"Set '{name}' as default handler")
        
        self.system_logger.info(f"Registered handler: {name} ({handler.__class__.__name__})")

    def unregister_handler(self, name: str) -> bool:
        """
        Unregisters a handler from the registry.

        This method removes a handler by its name. If the handler being removed is the current default,
        a new default handler will be automatically assigned if available.

        Args:
            name (str): The name of the handler to remove.

        Returns:
            bool: True if the handler was successfully removed, False if it was not found.
        """
        
        if name not in self.handlers:
            self.system_logger.warning(f"Handler '{name}' not found for removal")
            return False
        
        del self.handlers[name]
        
        # If this was the default handler, clear default
        if self.default_handler == name:
            self.default_handler = None
            # Set first available handler as default
            if self.handlers:
                self.default_handler = next(iter(self.handlers))
                self.system_logger.info(f"New default handler: {self.default_handler}")
        
        self.system_logger.info(f"Unregistered handler: {name}")
        return True
    
    def get_handler(self, name: str) -> Optional[BaseHandler]:
        """
        Retrieves a handler instance by its name.

        Args:
            name (str): The name of the handler to retrieve.

        Returns:
            Optional[BaseHandler]: The handler instance if found, otherwise None.
        """
        return self.handlers.get(name)
    
    def get_default_handler(self) -> Optional[BaseHandler]:
        """
        Retrieves the default handler instance.

        Returns:
            Optional[BaseHandler]: The default handler instance if one is set, otherwise None.
        """
        if self.default_handler:
            return self.handlers.get(self.default_handler)
        return None
    
    def set_default_handler(self, name: str) -> bool:
        """
        Sets a registered handler as the new default handler.

        Args:
            name (str): The name of the handler to set as default.

        Returns:
            bool: True if the default handler was successfully changed, False if the handler was not found in the registry.
        """
        if name not in self.handlers:
            self.system_logger.error(f"Cannot set default: handler '{name}' not found")
            return False
        
        self.default_handler = name
        self.system_logger.info(f"Default handler changed to: {name}")
        return True
    
    def enable_handler(self, name: str) -> bool:
        """
        Enables a specific handler.

        Calls the `enable` method on the handler instance if it exists in the registry.

        Args:
            name (str): The name of the handler to enable.

        Returns:
            bool: True if the handler was successfully enabled, False if not found.
        """
        handler = self.get_handler(name)
        if handler:
            handler.enable()
            self.system_logger.info(f"Handler '{name}' enabled")
            return True
        return False
    
    def disable_handler(self, name: str) -> bool:
        """
        Disables a specific handler.

        Calls the `disable` method on the handler instance if it exists in the registry.

        Args:
            name (str): The name of the handler to disable.

        Returns:
            bool: True if the handler was successfully disabled, False if not found.
        """
        handler = self.get_handler(name)
        if handler:
            handler.disable()
            self.system_logger.info(f"Handler '{name}' disabled")
            return True
        return False
    
    def get_handler_names(self) -> List[str]:
        """
        Retrieves a list of all registered handler names.

        Returns:
            List[str]: A list containing the names of all handlers currently in the registry.
        """
        return list(self.handlers.keys())
    
    def get_handler_info(self) -> List[Dict[str, Any]]:
        """
        Retrieves detailed information for all registered handlers.

        This method iterates through all handlers and calls their `get_info` method to compile a list of dictionaries with handler details.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains information about a handler, including a key `is_default` indicating if it is the current default.
        """
        info_list = []
        for name, handler in self.handlers.items():
            handler_info = handler.get_info()
            handler_info["is_default"] = (name == self.default_handler)
            info_list.append(handler_info)
        
        return info_list
    
    def get_enabled_handlers(self) -> List[str]:
        """
        Retrieves a list of names for all currently enabled handlers.

        Returns:
            List[str]: A list of names for handlers whose `enabled` attribute is True.
        """
        return [name for name, handler in self.handlers.items() if handler.enabled]
    
    def get_disabled_handlers(self) -> List[str]:
        """
        Retrieves a list of names for all currently disabled handlers.

        Returns:
            List[str]: A list of names for handlers whose `enabled` attribute is False.
        """
        return [name for name, handler in self.handlers.items() if not handler.enabled]
    
    def clear_all_handlers(self):
        """
        Clears all handlers from the registry.

        This method removes all registered handlers and resets the default handler to None.
        """
        self.handlers.clear()
        self.default_handler = None
        self.system_logger.info("All handlers cleared from registry")