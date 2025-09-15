import re

from typing import Optional, Dict, Any, Union
from botbuilder.core import TurnContext, MessageFactory
from botbuilder.core.teams import TeamsInfo
from botbuilder.schema import Attachment
from logging import Logger

from src.ms_teams.handlers.base_handler import BaseHandler
from src.auth.manager import AuthManager, UserRole, Permission
from src.auth.middleware import AuthMiddleware
from src.log.system_logger import Logger, get_system_logger

class AdminHandler(BaseHandler):
    """
    Handles administrative commands for user and system management.

    This handler processes commands prefixed with "/{prefix}" to perform
    actions such as listing users, adding or removing users, and changing
    user roles. It requires a user to be authenticated and possess the
    `ADMIN_COMMANDS` permission to function.

    Features:
        - Processes a variety of administrative commands.
        - Integrates with an `AuthManager` for user data manipulation.
        - Validates user permissions before command execution.
        - Provides a formatted help response via an Adaptive Card.

    Attributes:
        auth_manager (AuthManager): The manager responsible for user authentication.
        auth_middleware (AuthMiddleware): The middleware for handling authorization.
        prefix (str): The command prefix used to trigger this handler, e.g., "admin".
        permission (Permission): The required permission level for a user to access this handler.
        system_logger (Logger): A logger for recording system and command events.
        commands (Dict[str, Callable]): A mapping of command strings to their
                                        corresponding handler methods.

    Available commands:
        - /{prefix} status - System status
        - /{prefix} users - List users
        - /{prefix} add <user_id> <name> <email> <role> - Add user
        - /{prefix} remove <user_id> - Remove user
        - /{prefix} role <user_id> <new_role> - Change role
        - /{prefix} members - List all members of the current chat
    """
    def __init__(
            self,
            auth_manager: AuthManager,
            auth_middleware: AuthMiddleware,
            prefix: str,
            permission: Permission,
            name: str,
            description: str):
        """
        Initializes a new instance of the AdminHandler.

        Args:
            auth_manager (AuthManager): An instance of the authentication manager.
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
        self.auth_manager: AuthManager = auth_manager
        self.auth_middleware: AuthMiddleware = auth_middleware
        self.permission: Permission = permission
        self.system_logger: Logger = get_system_logger(__name__)

        # Mapeo de comandos
        self.commands = {
            "status": self._cmd_status,
            "users": self._cmd_users,
            "add": self._cmd_add_user,
            "remove": self._cmd_remove_user,
            "role": self._cmd_change_role,
            "members": self._cmd_members,
        }

    async def handle_message(self, turn_context: TurnContext) -> Optional[Union[str, Attachment]]:
        """
        Processes an incoming message to execute an administrative command.

        This method first checks for user authorization then determines if the message is a 
        specific admin command (prefixed with "/{prefix}"), it parses the message and
        dispatches it to the appropriate command handler.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            Optional[Union[str, Attachment]]: The response message as a string or
                                            an `Attachment`, or `None` if the
                                            handler is not enabled.
        """
        if not self.enabled:
            return None

        # Verificar autenticación y permisos de admin
        is_authorized, error_msg = await self.auth_middleware.process_message(
            turn_context,
            self.permission
        )

        if not is_authorized:
            return error_msg

        message = self._get_user_message(turn_context)

        # Parsear comando
        parts = message.strip().split(maxsplit=2)
        if len(parts) < 2 or parts[0].lower() != f"/{self.prefix}":
            return None

        command = parts[1].lower()
        args = parts[2] if len(parts) > 2 else ""

        user_info = self.auth_middleware.get_user_info(turn_context)
        user_name = user_info['name'] if user_info else "Unknown"
        user_role = user_info['role'] if user_info else "Unknown"

        self.system_logger.info(
            f"ADMIN - User: {user_name} ({user_role}) "
            f"Command: {command}"
        )

        # Ejecutar comando
        if command in self.commands:
            try:
                return await self.commands[command](args, turn_context)
            except Exception as e:
                self.system_logger.error(f"Error executing admin command '{command}': {e}", exc_info=True)
                return f"Error ejecutando comando '{command}': {str(e)}"
        else:
            return self._format_unknown_command(command)
        
    def _format_unknown_command(self, command: str) -> str:
        """
        Formats a response message for an unrecognized administrative command.

        Args:
            command (str): The unknown command entered by the user.

        Returns:
            str: A formatted error message.
        """
        return f"**Comando desconocido:** `/{self.prefix} {command}`. Usa `/{self.prefix} help` para ver los comandos disponibles.".strip()
    
    async def _cmd_status(self, args:str, turn_context: TurnContext) -> str:
        """
        Handles the "/{prefix} status" command.

        This command is intended to show the system's status.

        Args:
            args (str): The command arguments (not used).
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: A message indicating that the command is not implemented.
        """
        self.system_logger.warning(f"Command /{self.prefix} status requested, but not implemented.")
        return "NO IMPLEMENTADO: Estado del sistema."
    
    async def _cmd_users(self, args: str, turn_context: TurnContext) -> str:
        """
        Handles the "/{prefix} users" command.

        This command is intended to list all authorized users but is currently
        not implemented.

        Args:
            args (str): The command arguments (not used).
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: A message indicating that the command is not implemented.
        """
        self.system_logger.warning(f"Command /{self.prefix} users requested, but not implemented.")
        return "NO IMPLEMENTADO: Listar usuarios."
    
    async def _cmd_add_user(self, args, turn_context: TurnContext) -> str:
        """
        Handles the "/{prefix} add <user_id> <"name"> <email> <role>" command to add a new authorized user.

        Args:
            args (str): A string containing the user ID, name, email, and role.
            turn_context (TurnContext): The Bot Framework turn context to get the admin's info.

        Returns:
            str: A success or error message confirming the operation.
        """
        args = self._parse_user_string(args)
        if args is None:
            error_message = f"""
            Uso incorrecto\n
            - **Formato:** `/{self.prefix} add <user_id> <name> <email> <role>`\n
            - **Roles disponibles:** admin, medic, user, guest
            """
            return error_message.strip()
        
        user_id, user_name, user_email, role_str = args
        admin_info = self.auth_middleware.get_user_info(turn_context)
        admin_name = admin_info['name'] if admin_info else "Unknown Admin"

        # Validar rol
        try:
            user_role = UserRole(role_str.lower())
        except ValueError:
            return f"**Rol inválido:** `{role_str}`. **Roles válidos:** admin, user, guest".strip()

        # Verificar si ya existe
        if user_id in self.auth_manager.authorized_users:
            return f"**Usuario ya existe:** {user_name} (`{user_id}`)".strip()
        
        # Agregar usuario
        success = self.auth_manager.add_authorized_user(
            user_id=user_id,
            name=user_name,
            email=user_email,
            role=user_role,
            added_by=admin_name
        )
        
        if success:
            self.system_logger.info(f"User added: {user_name} ({user_id}) by {admin_name}")
            return f"""
            **Usuario agregado exitosamente**\n
            - **Nombre:** {user_name}\n
            - **ID:** {user_id}\n
            - **Email:** {user_email}\n
            - **Rol:** {user_role.value}\n
            - **Agregado por:** {admin_name}
            """.strip()
        else:
            self.system_logger.error(f"Error adding user: {user_name} ({user_id})")
            return f"**Error agregando usuario:** {user_name} (`{user_id}`)"
        
    async def _cmd_remove_user(self, args:str, turn_context: TurnContext) -> str:
        """
        Handles the "/{prefix} remove <user_id>" command to remove an authorized user.

        Args:
            args (str): The user ID of the user to remove.
            turn_context (TurnContext): The Bot Framework turn context to get the admin's info.

        Returns:
            str: A success or error message confirming the operation.
        """
        args = args.strip().split()

        if len(args) != 1:
            return f"**Uso incorrecto:** `/{self.prefix} remove <user_id>`".strip()
        
        user_id = args[0]
        
        # Verificar que existe
        if user_id not in self.auth_manager.authorized_users:
            error_message = f"**Usuario no encontrado:** `{user_id}`"
            return error_message.strip()
        
        user_id = args[0]
        admin_info = self.auth_middleware.get_user_info(turn_context)
        admin_id = admin_info['user_id'] if admin_info else ""
        admin_name = admin_info['name'] if admin_info else "Unknown Admin"

        if user_id == admin_id:
            return "**No puedes remover tu propia cuenta de administrador.**".strip()

        if user_id not in self.auth_manager.authorized_users:
            return f"**Usuario no encontrado:** `{user_id}`".strip()

        user_data = self.auth_manager.authorized_users[user_id]
        user_name = user_data.get("name", "Unknown")
        user_email = user_data.get("email", "")
        user_role = user_data.get("role", "")

        success = self.auth_manager.remove_authorized_user(user_id, admin_name)

        if success:
            self.system_logger.info(f"User removed: {user_name} ({user_id}) by {admin_name}")
            return f"""
            **Usuario removido exitosamente**\n
            - **Nombre:** {user_name}\n
            - **ID:** {user_id}\n
            - **Email:** {user_email}\n
            - **Rol:** {user_role.value}\n
            - **Removido por:** {admin_name}
            """.strip()
        else:
            self.system_logger.error(f"Error removing user: {user_name} ({user_id})")
            return f"**Error removiendo usuario:** {user_name} (`{user_id}`)"
        
    async def _cmd_change_role(self, args:str, turn_context: TurnContext) -> str:
        """
        Handles the "/{prefix} role <user_id> <new_role>" command to change an existing user's role.

        Args:
            args (str): A string containing the user ID and the new role.
            turn_context (TurnContext): The Bot Framework turn context to get the admin's info.

        Returns:
            str: A success or error message confirming the role change.
        """
        args = args.strip().split()
        
        if len(args) != 2:
            error_message = f"""
            **Uso incorrecto**\n\n
            **Formato:** `/{self.prefix} role <user_id> <new_role>`\n\n
            **Roles disponibles:** admin, medic, user, guest, banned
            """
            return error_message.strip()
        
        user_id = args[0]
        role_str = args[1].lower()
        admin_info = self.auth_middleware.get_user_info(turn_context)
        admin_name = admin_info['name'] if admin_info else "Unknown Admin"
        
        # Validar rol
        try:
            new_role = UserRole(role_str)
        except ValueError:
            return f"**Rol inválido:** `{role_str}`. **Roles válidos:** admin, medic, user, guest, banned".strip()

        # Verificar que el usuario existe
        if user_id not in self.auth_manager.authorized_users:
            return f"**Usuario no encontrado:** `{user_id}`".strip()

        # Obtener información del usuario
        user_data = self.auth_manager.authorized_users[user_id]
        user_name = user_data.get("name", "Unknown")
        old_role = user_data.get("role", UserRole.GUEST.value) # Asume guest si no tiene rol
        
        # Actualizar rol
        success = self.auth_manager.update_user_role(user_id, new_role, admin_name)

        if success:
            self.system_logger.info(
                f"Role updated for {user_name} ({user_id}): from {old_role} to {new_role.value} by {admin_name}"
            )
            return f"""
            **Rol actualizado exitosamente**\n
            - **Usuario:** {user_name}\n
            - **ID:** {user_id}\n
            - **Rol anterior:** {old_role}\n
            - **Rol nuevo:** {new_role.value}\n
            - **Actualizado por:** {admin_name}
            """.strip()
        else:
            self.system_logger.error(f"Error updating role for: {user_name} ({user_id})")
            return f"**Error actualizando rol para:** {user_name} (`{user_id}`)"
    
    async def _cmd_members(self, args: str, turn_context: TurnContext) -> str:
        """
        Handles the "/{prefix} members" command.

        This command retrieves all members of the current Microsoft Teams chat
        (not just authorized users) and returns their IDs and display names.

        Args:
            args (str): The command arguments (not used).
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: A formatted list of chat members with their IDs and names.
        """
        members = await TeamsInfo.get_members(turn_context)
        if not members:
            return "No se encontraron miembros en este chat."

        count = len(members)
        header = f"Se encontraron {count} usuario{'s' if count != 1 else ''} en este chat:\n"
        members_info = [f"- **{m.name}** | {m.id}" for m in members]

        return header + "\n".join(members_info)
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """
        Determines if the handler can process the given message.

        This method checks if the message begins with the "/{prefix}" prefix.

        Args:
            message (str): The user's message text.
            context (Dict[str, Any], optional): Additional contextual information.
                                                Defaults to None.

        Returns:
            bool: `True` if the message starts with "/{prefix}", otherwise `False`.
        """
        return message.strip().lower().startswith(f"/{self.prefix}")
    
    @staticmethod
    def _list_to_string_with_spaces(string_list: list) -> str:
        """
        Converts a list of strings into a single, space-separated string.

        Args:
            string_list (list): A list of strings.

        Returns:
            str: A single string with all list elements joined by spaces.
                Returns an empty string if the input is not a list or is empty.
        """
        if not isinstance(string_list, list):
            return ""
        return "".join(string_list)
    
    @staticmethod
    def _parse_user_string(user_string: str) -> Optional[list[str]]:
        """
        Extracts user details (ID, name, email, and role) from a formatted string.

        The expected format is: `<id> "<name>" <email> <role>`.

        Args:
            user_string (str): The input string containing the user details.

        Returns:
            Optional[list[str]]: A list containing the parsed user ID, name, email, and role.
                                Returns `None` if the string format is incorrect.
        """
        # Expresión regular para capturar:
        # 1. ID: uno o más caracteres alfanuméricos (incluyendo ':', '-') al principio
        # 2. Nombre: cualquier cosa entre comillas dobles
        # 3. Email: formato estándar de dirección de email
        # 4. Tipo de usuario/rol: una palabra al final
        match = re.search(r'([\w:-]+)\s+"([^"]+)"\s+([\w\.-]+@[\w\.-]+)\s+(\w+)', user_string)

        if match:
            user_id = match.group(1)
            name = match.group(2)
            email = match.group(3)
            user_type = match.group(4)
            return [user_id, name, email, user_type]
        else:
            return None
        
    def get_help(self) -> Dict[str, Any]:
        """
        Returns a detailed help dictionary for the AdminHandler.

        Returns:
            Dict[str, Any]: A dictionary containing structured help information.
        """
        return {
            "general_explanation": "Permite gestionar usuarios y permisos dentro del sistema. Requiere permisos de administrador.",
            "functionality": [
                "Gestiona los usuarios y sus roles.",
                "Permite añadir, eliminar y modificar usuarios.",
            ],
            "commands": [
                {
                    "name": "add",
                    "use": f"/{self.prefix} add <id> \"<nombre>\" <email> <rol>",
                    "description": "Añade un nuevo usuario."
                },
                {
                    "name": "remove",
                    "use": f"/{self.prefix} remove <id>",
                    "description": "Elimina un usuario existente."
                },
                {
                    "name": "role",
                    "use": f"/{self.prefix} role <id> <rol>",
                    "description": "Cambia el rol de un usuario."
                },
                {
                    "name": "members",
                    "use": f"/{self.prefix} members",
                    "description": "Lista todos los miembros del chat actual de Microsoft Teams"
                },
                {
                    "name": "list",
                    "use": f"/{self.prefix} list",
                    "description": "Muestra una lista de todos los usuarios registrados y sus roles."
                }
            ]
        }