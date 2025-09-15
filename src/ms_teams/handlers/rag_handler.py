import time
from typing import Optional, Dict, Any
from pathlib import Path
from botbuilder.core import TurnContext
from logging import Logger

from src.ms_teams.handlers.base_handler import BaseHandler
from src.auth.manager import AuthManager, Permission
from src.auth.middleware import AuthMiddleware
from src.lang_chain.open_ai_chat_runnable import OpenAIChatRunnable
from src.lang_chain.open_ai_chat_wrapper import OpenAIChatWrapper
from src.stats.stats_manager import StatsManager
from src.lang_chain.memory_manager import MemoryManager
from src.open_ai.client import OpenAIClient
from src.log.system_logger import Logger, get_system_logger
from src.config.settings import Settings, get_settings
from src.utils.txt import load_txt
from src.ms_teams.handlers.utils import extract_response

class RAGHandler(BaseHandler):
    """
    Manages interactions with a Retrieval-Augmented Generation (RAG) language model.

    This class provides a specialized handler for RAG capabilities, allowing
    each user to have their own dedicated conversation thread to maintain
    context. It includes a command to clear the conversation history and
    ensures that only authenticated users with the correct permissions
    can access the RAG model.

    Features:
        - Dedicated RAG conversation threads for each user.
        - User authentication and permission checks.
        - Extensible command-based architecture.
        - Extensible pre- and post-processing hooks.
        - Usage statistics tracking.

    Attributes:
        settings (Settings): Application settings.
        auth_manager (AuthManager): The manager for user authentication.
        auth_middleware (AuthMiddleware): The middleware for handling authorization.
        openai_vector_store_id (str): The ID of the OpenAI vector store used for file search.
        prefix (str): The command prefix used to trigger this handler, e.g., "rag".
        permission (Permission): The required permission level for a user to access this handler.
        system_logger (Logger): A logger for recording system and command events.
        user_rag_models (Dict[str, OpenAIAssistant]): A dictionary to store the RAG model instance for each user.
        openai_client (OpenAIClient): The client for interacting with the OpenAI API.
        commands (Dict[str, Callable]): A mapping of command strings to their corresponding handler methods.
        memory_manager (MemoryManager): Manages shared conversation memory for all user models.
        stats_manager (StatsManager): Manages the logging of usage statistics.
    """
    def __init__(
            self,
            auth_manager: AuthManager,
            auth_middleware: AuthMiddleware,
            openai_vector_store_id: str,
            prefix: str,
            permission: Permission,
            name: str,
            description: str,
            stats_manager: StatsManager,
            memory_manager: MemoryManager,
            templates_dir: Optional[str] = None,
            instructions_file: Optional[str] = None):
        """
        Initializes a new instance of the RAGHandler.

        Args:
            auth_manager (AuthManager): An instance of the authentication manager.
            auth_middleware (AuthMiddleware): An instance of the authentication middleware.
            openai_vector_store_id (str): The ID of the OpenAI vector store.
            prefix (str): The command prefix for the handler.
            permission (Permission): The permission required to use the handler. 
            name (str): The unique identifier or name of the handler.
            description (str): A brief description of the handler's purpose.
            stats_manager (StatsManager): The manager for logging usage statistics.
            memory_manager (MemoryManager): The centralized manager for conversation memory.
            templates_dir (Optional[str]): The directory path where prompt templates are stored as .txt files.
            instructions_file (Optional, str): The .txt file used to configure the LLM's behavior with system instructions. Defaults to "_instructions.txt".
        """
        super().__init__(
            name=name,
            prefix=prefix,
            description=description,
        )
        self.settings: Settings = get_settings()
        self.auth_manager: AuthManager = auth_manager
        self.auth_middleware: AuthMiddleware = auth_middleware
        self.openai_vector_store_id: str = openai_vector_store_id
        self.permission: Permission = permission
        self.system_logger: Logger = get_system_logger(__name__)
        self.user_rag_models: Dict[str, OpenAIChatRunnable] = {}
        self.stats_manager: StatsManager = stats_manager
        self.memory_manager: MemoryManager = memory_manager
        self._templates_dir: str = templates_dir if templates_dir else str(Path(self.settings.templates_dir) / "rag")
        self._instructions_file: str = instructions_file if instructions_file else "_instructions.txt"
        self.openai_client = OpenAIClient(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model_name,
            instructions=load_txt(str(Path(self._templates_dir) / self._instructions_file)),
            tools=None,
            temperature=self.settings.llm_temperature,
            max_output_tokens=self.settings.llm_max_output_tokens)

        # Mapeo de comandos
        self.commands = {
        }

    async def _get_rag_model_for_user(self, user_info: Dict) -> OpenAIChatRunnable:
        """
        Retrieves or creates an `OpenAIChatRunnable` instance for the current user.

        Each user is assigned their own RAG assistant thread to maintain a
        persistent conversation context. This method ensures that the correct
        instance is retrieved or a new one is created if one does not exist.

        Args:
            user_info (Dict): A dictionary containing the authenticated user's
                            information, including 'user_id' and 'name'.

        Returns:
            OpenAIChatRunnable: The RAG model instance associated with the user.
        """
        user_id = user_info['user_id']
        user_name = user_info['name']

        if user_id not in self.user_rag_models:
            self.system_logger.debug(f"Creating new OpenAIChatRunnable for RAG user: {user_name}")

            llm = OpenAIChatWrapper(client=self.openai_client)

            def history_getter(session_id: str):
                return self.memory_manager.get_history_for_user(session_id)
            
            tools = [
                OpenAIClient.tool_file_search(vector_store_ids=[self.openai_vector_store_id]),
            ]

            runnable = OpenAIChatRunnable(
                llm=llm,
                history_getter=history_getter,
                tools=tools,
                system_instructions=self.openai_client.instructions,
            )

            self.user_rag_models[user_id] = runnable

        return self.user_rag_models[user_id]

    
    async def handle_message(self, turn_context: TurnContext) -> Optional[str]:
        """
        Handles incoming message, handling both general and command-based
        RAG requests.

        This method first checks for user authorization and then determines
        if the message is a specific RAG command (prefixed with "/{prefix}").
        If it's a command, it dispatches it to the appropriate method.
        Otherwise, it treats the message as a general query for the RAG model.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            Optional[str]: The response generated for the user, or `None` if
                        the handler is not enabled.
        """
        if not self.enabled:
            return None

        is_authorized, error_msg = await self.auth_middleware.process_message(
            turn_context,
            self.permission
        )

        if not is_authorized:
            return error_msg

        message = self._get_user_message(turn_context).strip()

        if message.startswith(f"/{self.prefix}"):

            parts = message.split(maxsplit=2)
            if len(parts) < 2:
                return f"Comando incompleto. Uso: /{self.prefix} <comando> [argumentos]"
            
            command = parts[1].lower()
            args = parts[2] if len(parts) > 2 else ""

            if command in self.commands:
                return await self._execute_command(command, args, turn_context)
            else:
                user_info = self.auth_middleware.get_user_info(turn_context)
                start_time = time.time()
                response = await self._process_message(turn_context, message.removeprefix(f"/{self.prefix}").strip())
                response = response if response else ""
                duration_ms = (time.time() - start_time) * 1000
                self.stats_manager.log(
                user_info, f"{self.prefix}", self.name, None, duration_ms, "success"
                )
                return extract_response(response)

        elif message.startswith("/"):
            parts = message.split(maxsplit=1)

            command = parts[0].removeprefix("/").lower()
            args = parts[1] if len(parts) > 1 else ""

            if command in self.commands:
                return await self._execute_command(command, args, turn_context)
            else:
                user_info = self.auth_middleware.get_user_info(turn_context)
                start_time = time.time()
                response = await self._process_message(turn_context, message.strip("/"))
                response = response if response else ""
                duration_ms = (time.time() - start_time) * 1000
                self.stats_manager.log(
                user_info, f"{self.prefix}", self.name, None, duration_ms, "success"
                )
                return extract_response(response)

        else:
            user_info = self.auth_middleware.get_user_info(turn_context)
            start_time = time.time()
            response = await self._process_message(turn_context, message)
            response = response if response else ""
            duration_ms = (time.time() - start_time) * 1000
            self.stats_manager.log(
            user_info, f"{self.prefix}", self.name, None, duration_ms, "success"
            )
            return extract_response(response)

    async def _execute_command(self, command: str, args: str, turn_context: TurnContext) -> str:
        """
        Executes a specific command from the handler's command map.

        This helper function centralizes the logic for executing a command
        method, handling potential exceptions, and formatting the response.

        Args:
            command (str): The name of the command to execute.
            args (str): The arguments to pass to the command function.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The response from the executed command, or an error message if
                 the command fails.
        """
        try:
            user_info = self.auth_middleware.get_user_info(turn_context)
            start_time = time.time()
            response = await self.commands[command](args, turn_context)
            response = response if response else ""
            duration_ms = (time.time() - start_time) * 1000
            self.stats_manager.log(
                user_info, f"{self.prefix}_command", self.name, command, duration_ms, "success"
            )
            return extract_response(response)
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.stats_manager.log(
                user_info, f"{self.prefix}_command", self.name, command, duration_ms, "error"
            )
            self.system_logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            return f"Error ejecutando comando '{command}': {str(e)}"

    async def _process_message(self, turn_context: TurnContext, message: str) -> str:
        """
        Processes a general, non-command-based message for the RAG model.

        This method performs pre- and post-processing on the message before
        and after it is sent to the RAG model, ensuring proper logging and
        error handling.

        Args:
            turn_context (TurnContext): The Bot Framework turn context.
            message (str): The user's message text (without the "/{prefix}" prefix).

        Returns:
            str: The final, processed response from the RAG model.
        """
        try:
            user_info = self.auth_middleware.get_user_info(turn_context) 
            if not user_info:
                return "Error obteniendo información de usuario."

            self.system_logger.debug(
                f"RAG {self.name} - User: {user_info['name']} ({user_info['role']}) "
                f"Input: {message}"
            )

            processed_message = await self._pre_process(message, turn_context)
            rag_response = await self._create_response(
                processed_message,
                user_info
            )
            final_response = await self._post_process(rag_response, message, turn_context)

            self.system_logger.debug(
                f"RAG {self.name} - Response: {user_info['name']} ({user_info['role']}) "
                f"Output: {final_response}"
            )
            return final_response

        except Exception as e:
            self.system_logger.error(f"Error in RAG {self.name} handler: {e}", exc_info=True)
            return "Error procesando tu mensaje. Por favor intenta de nuevo."
    
    async def _create_response(self, message: str, user_info: Dict) -> str:
        """
        Generates a response from the RAG model.

        Args:
            message (str): The pre-processed message to send to the RAG model.
            user_info (Dict): A dictionary containing authenticated user information.

        Returns:
            str: The raw response generated by the RAG model.
        """
        rag = await self._get_rag_model_for_user(user_info)
        response = await rag.ainvoke(
            message,
            config={"configurable": {"session_id": user_info["user_id"]}}
        )
        return response.get("response")
    
    async def _pre_process(self, message: str, turn_context: TurnContext) -> str:
        """
        Pre-processes a message before it is sent to the RAG model.

        This is a hook for subclasses to implement custom pre-processing logic,
        such as adding additional context or cleaning the message.

        Args:
            message (str): The original user message.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The processed message.
        """
        return message.strip()

    async def _post_process(self, rag_response: str, original_message: str, turn_context: TurnContext) -> str:
        """
        Post-processes the RAG model's response before sending it to the user.

        This method is a hook for subclasses to format the response, add
        additional details, or perform other final modifications.

        Args:
            rag_response (str): The raw response from the RAG model.
            original_message (str): The original user message.
            turn_context (TurnContext): The Bot Framework turn context.

        Returns:
            str: The final, formatted response for the user.
        """
        return rag_response.strip()
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """
        Determines if this handler can process the given message.

        The RAG handler is designed to handle messages that either begin with
        the "/{prefix}" prefix or are not explicit commands for other specialized
        handlers.

        Args:
            message (str): The user's message text.
            context (Dict[str, Any], optional): Additional contextual information.
                                                Defaults to None.

        Returns:
            bool: `True` if the message can be handled by this handler,
                otherwise `False`.
        """
        return message.strip().lower().startswith(f"/{self.prefix}")
    
    def get_help(self) -> Dict[str, Any]:
        """
        Returns a detailed help dictionary for the RAGHandler.

        Returns:
            Dict[str, Any]: A dictionary containing structured help information.
        """
        return {
            "general_explanation": "Se encarga de las conversaciones basadas en documentos y archivos de información, utilizando un modelo de lenguaje con recuperación aumentada (RAG).",
            "functionality": [
                "Responde preguntas utilizando los documentos disponibles en tu base de conocimiento."
            ],
            "commands": [
                {
                    "name": "message",
                    "use": f"/{self.prefix} <mensaje>",
                    "description": "Envia una mensaje al modelo de lenguaje."
                }
            ]
        }