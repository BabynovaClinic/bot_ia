from datetime import datetime
from typing import Optional, Dict, Any
from botbuilder.core import TurnContext
from logging import Logger

from src.ms_teams.handlers.base_handler import BaseHandler
from src.auth.manager import Permission
from src.auth.middleware import AuthMiddleware
from src.log.system_logger import Logger, get_system_logger

class EchoHandler(BaseHandler):
    """
    Manages the "echo" functionality with built-in authentication.

    This class is a dedicated handler for echoing a user's message back to
    them. It automatically verifies user permissions and generates a
    customized response that includes user-specific information. It supports
    message pre- and post-processing for extended functionality.

    Features:
        - Automatic permission verification for "echo" mode usage.
        - Personalized response generation with user details.
        - Detailed user activity logging.
        - Extensible pre- and post-processing hooks.

    Attributes:
        auth_middleware (AuthMiddleware): The middleware for handling authorization.
        prefix (str): The command prefix used to trigger this handler, e.g., "echo".
        permission (Permission): The required permission level for a user to access this handler.
        system_logger (Logger): A logger for recording system and user activity.
    """
    def __init__(
            self,
            auth_middleware: AuthMiddleware,
            prefix: str,
            permission: Permission,
            name: str,
            description: str):
        """
        Initializes a new instance of the EchoHandler.

        Args:
            auth_middleware (AuthMiddleware): An instance of the authentication middleware.
            prefix (str): The command prefix for the handler.
            permission (Permission): The permission required to use the handler.
            name (str): The unique identifier or name of the handler.
            description (str): A brief description of the handler's purpose.
        """
        super().__init__(
            name=name,
            prefix=prefix,
            description=description
        )
        self.auth_middleware: AuthMiddleware = auth_middleware
        self.permission: Permission = permission
        self.system_logger: Logger = get_system_logger(__name__)

    async def handle_message(self, turn_context: TurnContext) -> Optional[str]:
        """
        Handles incoming messages for the Echo handler.

        This method first checks for user authorization and then determines
        if the message is prefixed with "/{prefix}". Before processing the message and generating a response.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            Optional[str]: The response message to be sent to the user, or `None` if
                        the handler is not enabled or cannot process the message.
        """
        if not self.enabled:
            return None

        is_authorized, error_msg = await self.auth_middleware.process_message(
            turn_context,
            Permission.USE_ECHO
        )

        if not is_authorized:
            return error_msg

        message = self._get_user_message(turn_context)

        cleaned_message = message.removeprefix(f"/{self.prefix}").strip() 

        return await self._process_echo(cleaned_message, turn_context)

    
    async def _process_echo(self, message: str, turn_context: TurnContext) -> str:
        """
        Contains the core logic for the Echo handler after authentication.

        This method handles the pre-processing, response creation, and
        post-processing steps for an already authenticated and parsed message.

        Args:
            message (str): The user's message text, without the "/{prefix}" prefix.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The final formatted response for the user.
        """
        try:
            user_info = self.auth_middleware.get_user_info(turn_context)
            user_name = user_info['name'] if user_info else "Unknown"
            user_role = user_info['role'] if user_info else "Unknown"

            if not user_info:
                return "Error obteniendo información de usuario."
            
            self.system_logger.debug(
            f"Echo - User: {user_name} ({user_role}) "
            f"Message: {message}"
        )

            processed_message = await self._pre_process(message, turn_context)

            echo_response = self._create_response(
                processed_message,
                user_info
            )

            final_response = await self._post_process(echo_response, message, turn_context)

            self.system_logger.debug(
                f"Echo - Response: {user_name} ({user_role}) "
                f"Response: {processed_message}"
            )

            return final_response

        except Exception as e:
            self.system_logger.error(f"Error in EchoHandler: {e}", exc_info=True)
            return "Error procesando tu mensaje. Por favor intenta de nuevo."

    
    def _create_response(self, message: str, user_info: Dict) -> str:
        """
        Creates a personalized "echo" response with user information.

        This method formats the response to include details such as the user's
        name and role, along with the echoed message, using relevant emojis.

        Args:
            message (str): The pre-processed message to be echoed.
            user_info (Dict): A dictionary containing the authenticated user's information.

        Returns:
            str: The formatted response with user and echo information.
        """
        role_emojis = {
            "admin": "👑",
            "user": "👤",
            "guest": "👥",
            "banned": "🚫" # Añadido para consistencia con UserRole
        }

        # Obtener el emoji basado en el rol del usuario, con un valor por defecto
        role_emoji = role_emojis.get(user_info.get("role", "guest"), "👤")

        # Construir la respuesta base
        response = f"🤖 **MSBot - Modo Echo**\n\n"

        # Añadir información del usuario
        response += f"{role_emoji} **Usuario:** {user_info.get('name', 'Usuario')}\n\n"
        response += f"🎭 **Rol:** {user_info.get('role', 'unknown').title()}\n\n"

        # Añadir la respuesta de eco
        response += f"🔄 **Respuesta Echo:** {message}\n\n"

        return response
    
    async def _pre_process(self, message: str, turn_context: TurnContext) -> str:
        """
        Pre-processes the message before it is echoed.

        This is a hook for subclasses to implement custom pre-processing logic,
        such as cleaning or normalizing the message text.

        Args:
            message (str): The original user message (without the prefix).
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The pre-processed message.
        """
        cleaned = message.strip()
        cleaned = ' '.join(cleaned.split()) # Elimina espacios múltiples
        return cleaned
    
    async def _post_process(self, response: str, original_message: str, turn_context: TurnContext) -> str:
        """
        Post-processes the echo response before it is sent to the user.

        This is a hook for subclasses to add additional information, such as a
        timestamp, to the final response.

        Args:
            response (str): The raw echo response.
            original_message (str): The original user message.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The final, formatted response for the user.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        final_response = response + f"\n\n⏰ **Procesado:** {timestamp}"

        return final_response
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """
        Determines if this handler can process a given message.

        The EchoHandler is designed to handle messages that explicitly
        begin with the "/{prefix}" prefix.

        Args:
            message (str): The user's message text.
            context (Dict[str, Any], optional): Additional contextual information.
                                                Defaults to None.

        Returns:
            bool: `True` if the message starts with "/{prefix}", otherwise `False`.
        """
        return message.strip().lower().startswith(f"/{self.prefix}")
    
    def get_help(self) -> Dict[str, Any]:
        """
        Returns a detailed help dictionary for the EchoHandler.

        Returns:
            Dict[str, Any]: A dictionary containing structured help information.
        """
        return {
            "general_explanation": "Repite tu mensaje. Es útil para verificar la conexión o para pruebas básicas.",
            "functionality": [
                "Repite cualquier mensaje que se le envíe."
            ],
            "commands": [
                {
                    "name": "message",
                    "use": f"/{self.prefix} <mensaje>",
                    "description": "Repite el mensaje que escribas después del comando."
                }
            ]
        }
    