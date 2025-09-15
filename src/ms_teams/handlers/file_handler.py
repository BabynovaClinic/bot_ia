import re
import time

from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Tuple
from logging import Logger
from botbuilder.core import TurnContext
from botbuilder.schema import Attachment

from src.ms_teams.handlers.base_handler import BaseHandler
from src.auth.manager import AuthManager, Permission
from src.auth.middleware import AuthMiddleware
from src.stats.stats_manager import StatsManager
from src.config.settings import Settings, get_settings
from src.log.system_logger import Logger, get_system_logger
from src.utils.json import load_json
from src.utils.txt import load_txt

class FileHandler(BaseHandler):
    """
    Handles file lookup requests from a JSON index based on document codes.

    This handler enables users to quickly retrieve documents if they know 
    the corresponding code (e.g., "FR-GC-01"). It supports both plain text 
    responses and Adaptive Card responses with clickable download links.

    Features:
        - Processes commands of the form "/{prefix} <code>".
        - Validates the format of the requested document code.
        - Retrieves and lists documents from a JSON index.
        - Returns both textual and card-based responses.

    Attributes:
        settings (Settings): Application settings.
        auth_manager (AuthManager): The authentication manager for user control.
        auth_middleware (AuthMiddleware): Middleware for processing user authorization.
        prefix (str): Command prefix to trigger this handler (e.g., "file").
        permission (Permission): The required permission to access this handler.
        system_logger (Logger): A logger for recording system events and errors.
        data (Dict[str, Any]): The in-memory representation of the loaded JSON index.
        stats_manager (StatsManager): Manages the logging of usage statistics.
    """

    def __init__(
        self,
        auth_manager: AuthManager,
        auth_middleware: AuthMiddleware,
        prefix: str,
        permission: Permission,
        name: str,
        description: str,
        stats_manager: StatsManager,
    ):
        """
        Initializes a new instance of the FileHandler.

        Args:
            auth_manager (AuthManager): The authentication manager instance.
            auth_middleware (AuthMiddleware): The middleware for authorization handling.
            prefix (str): The command prefix (e.g., "file").
            permission (Permission): The required permission to use this handler.
            name (str): The unique identifier of the handler.
            description (str): A brief description of the handler.
            stats_manager (StatsManager): The manager for logging usage statistics.
        """
        super().__init__(
            name=name,
            prefix=prefix,
            description=description
        )
        self.settings: Settings = get_settings()
        self.auth_manager: AuthManager = auth_manager
        self.auth_middleware: AuthMiddleware = auth_middleware
        self.permission: Permission = permission
        self.system_logger: Logger = get_system_logger(__name__)
        self.stats_manager: StatsManager = stats_manager
        self.data: Dict[str, Any] = load_json(self.settings.doc_meta_path)
        self._common_documents: Dict[str, Any] = load_json(str(Path(f"{self.settings.templates_dir}/file/documents.json")))
        self._common_template: str = load_txt(str(Path(f"{self.settings.templates_dir}/file/template.txt")))
        self._file_pattern: str = r"^[A-Z]{2}-[A-Z]{2}-\d{2}$"

    async def handle_message(self, turn_context: TurnContext) -> Optional[Union[str, Attachment]]:
        """
        Processes an incoming user message to handle file lookup requests.

        This method validates user permissions, checks command format, and 
        retrieves the corresponding documents from the JSON index.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            Optional[Union[str, Attachment]]: A formatted string or an Adaptive Card with results,
                                              or `None` if the handler does not apply.
        """
        if not self.enabled:
            return None

        is_authorized, error_msg = await self.auth_middleware.process_message(
            turn_context,
            self.permission
        )
        if not is_authorized:
            return error_msg

        message = self._get_user_message(turn_context)

        if message.strip().startswith(f"/{self.prefix}"):
            parts = message.strip().split(maxsplit=2)

            # Comandos comunes con /file
            if len(parts) < 2:
                return self._common_codes()

            # Busqueda de archivos
            else:
                command = parts[1]
                args = parts[2] if len(parts) > 2 else ""

                if re.match(self._file_pattern, command.upper().strip()):
                    code = command.upper().strip()
                    user_info = self.auth_middleware.get_user_info(turn_context)
                    start_time = time.time()
                    response, success  = self._search_documents(code)
                    duration_ms = (time.time() - start_time) * 1000

                    self.stats_manager.log(
                    user_info, f"{self.prefix}", self.name, None, duration_ms, "success" if success else "error"
                    )

                    return response 
                
                else:
                    return f"Formato de código no válido: {command}. Ejemplo: FR-GC-01"

    def _common_codes(self) -> str:
        """
        Formats and returns a list of frequently used document codes from a JSON index.

        This method generates a user-friendly, Markdown-formatted message
        that lists common document codes, their names, and descriptions.
        It also provides a reference to the master document list code.

        Returns:
            str: A formatted string containing the list of common documents.
        """
        # Load the template and common documents data
        prefix = self.prefix
        template = self._common_template
        data = self._common_documents

        # Create the list of documents with Markdown formatting
        documents_list = []
        for doc in data.get("documents", []):
            documents_list.append(f"- **`{doc['code']}`**: {doc['name']} - _{doc['description']}_")

        # Join the list into a single string
        documents_list_str = "\n\n".join(documents_list)
        print(documents_list_str)

        # Format the template with the data
        return template.format(
            prefix=prefix,
            documents_list=documents_list_str,
            master_document_code=data.get("master_document_code", "")
        )

    def _search_documents(self, code: str) -> Tuple[str, bool]:
        """
        Searches the stored JSON data for documents associated with a specific code.

        This function looks up a given document code and, if found, returns a formatted
        plain text message that includes the names and download links for all
        associated documents. It handles cases where no documents are found for the code.

        Args:
            code (str): The document code to search for (e.g., "FR-GC-01").

        Returns:
            Tuple[str, bool]: A tuple containing:
                - A plain text message with the search results, including document names and links.
                - A boolean value indicating if any documents were found (True) or not (False).
        """
        self.system_logger.debug(f"File - User: Search document with code {code}")

        docs: List[Dict[str, str]] = self.data.get(code, [])

        if not docs:
            self.system_logger.debug(f"File - Response: Not found document with code {code}")
            return f"No se encontraron documentos para el código `{code}`.", False

        header = f"🔎 Se {'encontraron' if len(docs) > 1 else 'encontro'} {len(docs)} documento{'s' if len(docs) > 1 else ''} para el código `{code}`:\n\n"

        doc_list = []
        for doc in docs:
            name = doc.get('name', 'Unnamed')
            url = doc.get('webUrl', '#')
            doc_list.append(f"- **{name}** [Descargar]({url})\n")

        self.system_logger.debug(f"File - Response: Found document with code {code}")

        return header + "\n".join(doc_list), True

    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """
        Determines if this handler can process the given message.

        Args:
            message (str): The user's message.
            context (Dict[str, Any], optional): Additional contextual information.

        Returns:
            bool: True if the message starts with the prefix, otherwise False.
        """
        return message.strip().lower().startswith(f"/{self.prefix}")
    
    def get_help(self) -> Dict[str, Any]:
        """
        Returns a detailed help dictionary for the FileHandler.

        Returns:
            Dict[str, Any]: A dictionary containing structured help information.
        """
        return {
            "general_explanation": "Permite buscar y acceder a documentos del sistema de gestión de calidad utilizando un código único.",
            "functionality": [
                "Busca documentos del sistema de gestión de calidad."
            ],
            "commands": [
                {
                    "name": "file",
                    "use": f"/{self.prefix} <code>",
                    "description": "Busca documentos asociados con un código específico. Los códigos deben seguir el formato `XX-XX-NN` (ej. `FR-GC-01`)."
                }
            ]
        }