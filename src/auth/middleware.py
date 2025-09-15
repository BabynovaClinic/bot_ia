from typing import Optional, Callable, Any, Tuple, Dict
from botbuilder.core import TurnContext

from src.auth.manager import AuthManager, Permission
from src.log.system_logger import Logger, get_system_logger

class AuthMiddleware:
    """
    Authentication middleware that runs before processing messages.

    This middleware handles user authentication and permission-based access control.
    
    Features:
        - Automatic user verification
        - Permission-based access control
        - Customized error messages
        - Logging of access attempts

    Attributes:
        auth_manager (AuthManager): Manages user authentication and permissions.
        system_logger (Logger): Logger instance for tracking access attempts and errors.
        error_messages (dict): Dictionary of customized error messages for different access scenarios.
    """
    
    def __init__(self, auth_manager: AuthManager):
        """
        Initializes the AuthMiddleware with an authentication manager.
        
        Args:
            auth_manager (AuthManager): An instance of AuthManager to handle user authentication.
        """
        self.auth_manager = auth_manager
        self.system_logger = get_system_logger(__name__)
        self.error_messages = {
            "unauthorized": "**Acceso No Autorizado**\n\nLo siento, no tienes permisos para usar este bot.\n\nPara obtener acceso, contacta a tu administrador con tu **ID**:\n\n{user_id}",
            "insufficient_permissions": "**Permisos Insuficientes**\n\nNo tienes los permisos necesarios para realizar esta acción.",
            "banned": "**Acceso Denegado**\n\nTu cuenta ha sido suspendida del uso de este bot."
        }

    async def process_message(self, context: TurnContext, required_permission: Permission = None) -> Tuple[bool, Optional[str]]:
        """
        Processes the message and verifies authentication and authorization.

        Args:
            context (TurnContext): The turn context for the current message.
            required_permission (Permission, optional): The permission required for the action. Defaults to None.
            
        Returns:
            Tuple[bool, Optional[str]]: A tuple containing an authorization status and an error message.
            - The first element is True if the user is authorized, False otherwise.
            - The second element is the error message if not authorized, otherwise None.
        """
        
        try:
            user_id = context.activity.from_property.id
            user_name = context.activity.from_property.name
            user_email = getattr(context.activity.from_property, 'email', None)
            
            self.system_logger.debug(f"Processing auth for user {user_name}")
            
            auth_user = self.auth_manager.authenticate_user(user_id, user_name, user_email)
            
            if not auth_user:
                error_msg = self.error_messages["unauthorized"].format(user_id=user_id)
                self.system_logger.warning(f"Unauthorized access attempt: {user_id} ({user_name})")
                return False, error_msg
            
            if auth_user.role.value == "banned":
                error_msg = self.error_messages["banned"]
                self.system_logger.warning(f"Banned user attempted access: {user_id}")
                return False, error_msg
            
            if required_permission and not auth_user.has_permission(required_permission):
                error_msg = self.error_messages["insufficient_permissions"].format(
                    role=auth_user.role.value,
                    permission=required_permission.value
                )
                self.system_logger.warning(f"Insufficient permissions for {user_id}: required {required_permission.value}")
                return False, error_msg
            
            self.system_logger.debug(f"User authorized {auth_user.name} with role {auth_user.role.value}")
            return True, None
            
        except Exception as e:
            self.system_logger.error(f"Error in auth middleware: {e}")
            error_msg = "Error interno de autenticación. Contacta al administrador."
            return False, error_msg
        
    def get_user_info(self, turn_context: TurnContext) -> Optional[Dict]:
        """
        Retrieves the authenticated user's information.

        Args:
            turn_context (TurnContext): The turn context for the current message.
            
        Returns:
            Optional[Dict]: A dictionary containing user information if authenticated, otherwise None.
        """
        try:
            user_id = turn_context.activity.from_property.id
            auth_user = self.auth_manager.get_authenticated_user(user_id)
            
            if auth_user:
                return auth_user.to_dict()
            
            return None
            
        except Exception as e:
            self.system_logger.error(f"Error getting user info: {e}")
            return None