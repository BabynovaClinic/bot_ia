from pathlib import Path
from typing import Dict, Any, List
from botbuilder.core import TurnContext

from src.ms_teams.handlers.base_handler import BaseHandler
from src.auth.manager import AuthManager, Permission
from src.auth.middleware import AuthMiddleware

class HelpHandler(BaseHandler):
    """
    Manages and provides help information to the user.

    This handler is responsible for generating and displaying help content
    dynamically, based on a general request or a specific command for a
    particular handler.

    Features:
        - Provides a general overview of all available commands.
        - Offers specific, detailed help for individual handlers.
        - Uses Adaptive Cards for a consistent and rich user interface.

    Attributes:
        auth_manager (AuthManager): The manager responsible for user authentication.
        auth_middleware (AuthMiddleware): The middleware for handling authorization.
    """

    def __init__(
            self,
            auth_manager: AuthManager,
            auth_middleware: AuthMiddleware,
            handlers: Dict[str, Dict],
            prefix: str,
            name: str,
            description: str):
        """
        Initializes a new instance of the HelpHandler.

        Args:
            prefix (str): The command prefix used to trigger this handler, e.g., "help".
            handlers (Dict[str, BaseHandler]): A dictionary mapping command prefixes to their
                                                corresponding handler instances. This is used
                                                to generate help content dynamically.
        """
        super().__init__(
            name=name,
            prefix=prefix,
            description=description
        )
        self.auth_manager: AuthManager = auth_manager
        self.auth_middleware: AuthMiddleware = auth_middleware
        self.handlers: Dict[str, Dict] = handlers
    
    async def handle_message(self, turn_context: TurnContext) -> str:
        """
        Handles the incoming help message and provides a response.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The help content string to be sent back to the user.
        """
        if not self.enabled:
            return None
        
        is_authorized, error_msg = await self.auth_middleware.process_message(turn_context)

        if not is_authorized:
            return error_msg
        
        user_info = self.auth_middleware.get_user_info(turn_context)
        permissions = user_info["permissions"] if user_info else []
        message = self._get_user_message(turn_context).strip().lower()

        parts = message.split()
        content = ""

        # Check for general help command
        if len(parts) == 1 and parts[0] == f"/{self.prefix}":
            content = self._generate_general_help(permissions)
        
        # Check for specific help command
        elif len(parts) == 2 and parts[0] == f"/{self.prefix}":
            handler_prefix = parts[1]
            if handler_prefix in self.handlers:
                handler_info = self.handlers[handler_prefix]
                required_permission = handler_info.get("permission")
                if required_permission is None or required_permission in permissions:
                    content = self._generate_specific_help(handler_info)
                else:
                    content = self._generate_error_help(handler_prefix, "No tienes permiso para acceder a información de este comando.")
            else:
                content = self._generate_error_help(handler_prefix)
              
        else:
            content = self._generate_error_help(message)

        return content

    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """
        Determines if this handler can process the given message.

        The handler is triggered by messages starting with the configured
        command prefix, e.g., "/help" or "/help <command>".

        Args:
            message (str): The user's message text.
            context (Dict[str, Any], optional): Additional contextual information.

        Returns:
            bool: `True` if the message is a valid help command, `False` otherwise.
        """
        return message.strip().lower().startswith(f"/{self.prefix}")

    def _generate_specific_help(self, handler_info: Dict[str, Any]) -> str:
        """
        Generates the help content for a specific handler.

        This method extracts help data from a handler instance or its info dictionary,
        and formats it into a readable string.

        Args:
            handler_info (Dict[str, Any]): The handler's information dictionary, containing
                                           the instance, prefix, and other data.

        Returns:
            str: The formatted help string for the specific handler.
        """
        handler_instance: BaseHandler = handler_info.get("instance")
        handler_prefix: str = handler_info.get("prefix")
        
        help_data = {}
        if handler_instance:
            help_data = handler_instance.get_help()

        metadata: Dict = handler_info.get("metadata", {}) 

        general_explanation = metadata.get("general_explanation", help_data.get('general_explanation', 'Not available.'))
        functionalities_list = metadata.get("functionality", help_data.get('functionality', []))
        commands_list = metadata.get("commands",help_data.get('commands', []))
        
        section = f"**Comando: /{handler_prefix}**\n\n"
        section += f"**Descripción General:** {general_explanation}\n\n"
        
        if functionalities_list:
            functionalities = "\n".join([f"- {func}" for func in functionalities_list])
            section += f"**Funcionalidades:**\n{functionalities}\n\n"
        
        if commands_list:
            commands = [f"- **Uso:** `{cmd['use']}` **Descripción:** {cmd['description']}" for cmd in commands_list]
            section += f"**Comandos:**\n" + "\n".join(commands)
        
        return section
    
    def _generate_general_help(self, permissions: List[Permission]) -> str:
        """
        Generates the content for the general help message, listing all
        available commands the user has permission to see.

        Args:
            permissions (List[Permission]): The user's permissions.

        Returns:
            str: The formatted general help string.
        """
        help_sections = []
        for _, handler_info in self.handlers.items():
            handler_permission = handler_info.get("permission")
            handler_name = handler_info.get("name")
            
            if handler_name in ["help", "echo"]:
                continue

            if handler_permission is None or handler_permission in permissions:
                section = self._generate_specific_help(handler_info)
                help_sections.append(section)

        if not help_sections:
            return "No hay comandos disponibles."

        return "\n\n---\n\n".join(help_sections)
    
    def _generate_error_help(self, command: str, reason: str = None) -> str:
        """
        Generates an error message for an unknown or unauthorized help command.

        Args:
            command (str): The unknown command provided by the user.
            reason (str, optional): A specific reason for the error, if applicable.
        
        Returns:
            str: The formatted error message.
        """
        if reason:
            return f"❌ **Error:** {reason}\n\nType `/{self.prefix}` for a list of available commands."
        else:
            return f"❌ **Error:** Command `/{self.prefix} {command}` not found.\n\nType `/{self.prefix}` for a list of available commands."


    def get_help(self) -> Dict[str, Any]:
        """
        Returns a detailed help dictionary for the HelpHandler.

        Returns:
            Dict[str, Any]: A dictionary containing structured help information.
        """
        return {
            "general_explanation": "Proporciona información sobre los manejadores (handlers) y comandos disponibles.",
            "functionality": [
                "Ofrece un resumen general de todos los comandos del sistema.",
                "Proporciona ayuda detallada sobre un comando específico.",
            ],
            "commands": [
                {
                    "name": "general",
                    "use": f"/{self.prefix}",
                    "description": "Muestra una lista completa de todos los comandos disponibles."
                },
                {
                    "name": "specific",
                    "use": f"/{self.prefix} <comando>",
                    "description": "Muestra una descripción detallada y los comandos de un manejador específico (ej. `/help admin`)."
                }
            ]
        }