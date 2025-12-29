
import traceback
import time
from logging import Logger
from typing import  Any, Optional, Dict, List
from pathlib import Path

from botbuilder.core import (
    TurnContext, 
    ActivityHandler, 
    MessageFactory,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings
)

from botbuilder.schema import Activity, Attachment, ChannelAccount

from src.auth.manager import AuthManager
from src.auth.middleware import AuthMiddleware
from src.auth.manager import AuthManager, Permission
from src.lang_chain.memory_manager import MemoryManager
from src.stats.stats_manager import StatsManager
from src.ms_teams.handler_registry.registry import HandlerRegistry
from src.ms_teams.handlers.base_handler import BaseHandler
from src.ms_teams.handlers.admin_handler import AdminHandler
from src.ms_teams.handlers.echo_handler import EchoHandler
from src.ms_teams.handlers.help_handler import HelpHandler
from src.ms_teams.handlers.file_handler import FileHandler
from src.ms_teams.handlers.llm_handler import LLMHandler
from src.ms_teams.handlers.rag_handler import RAGHandler
from src.open_ai.utils.check_assistant import check_assistant_by_id
from src.open_ai.utils.check_vector_store import check_vector_store_by_id
from src.config.settings import Settings, get_settings
from src.log.system_logger import Logger, get_system_logger
from src.log.user_logger import get_user_logger
from src.utils.yaml import load_yaml
from src.utils.txt import load_txt

class MSTeamsBot(ActivityHandler):
    """
    Main bot handler for Microsoft Teams.

    This class manages the core logic for processing incoming Teams activities,
    including authentication, routing messages to appropriate handlers, and
    managing user-specific loggers.

    Features:
        - Processes incoming activities from the Bot Framework Connector.
        - Routes messages to different handlers based on command prefixes.
        - Handles authentication and user-specific logging.
        - Provides a centralized error handling mechanism for bot activities.
        - Usage statistics tracking.

    Attributes:
        settings (Settings): Application settings.
        system_logger (Logger): Logger for system-wide events.
        stats_manager (StatsManager): Manages the logging of usage statistics.
        user_loggers (dict): A dictionary to store loggers for individual users.
        auth_manager (AuthManager): Manages user authentication.
        auth_middleware (AuthMiddleware): Middleware for authentication checks.
        adapter (BotFrameworkAdapter): Adapter for processing bot activities.
        handler_registry (HandlerRegistry): Registry for message handlers.
        memory_manager (MemoryManager): The centralized manager for conversation memory.
    """
    def __init__(self, auth_manager: AuthManager = None, auth_middleware: AuthMiddleware = None):
        """
        Initializes the MSTeamsBot instance.

        This constructor sets up the bot's core components, including application
        settings, loggers, authentication managers, the Bot Framework Adapter,
        and the message handler registry. It also performs an initial check for
        the configured OpenAI assistant.

        Args:
            auth_manager (AuthManager, optional): An instance of the authentication manager.
                                                 Defaults to a new instance if not provided.
            auth_middleware (AuthMiddleware, optional): An instance of the authentication middleware.
                                                        Defaults to a new instance if not provided.
        """
        super().__init__()
        self.settings: Settings = get_settings()
        self._hanlder_map: Dict[str, Dict] = load_yaml(str(Path(self.settings.handler_cfg_path)))
        self._welcome_template: str = load_txt(str(Path(self.settings.templates_dir) / "welcome/template.txt"))
        self.system_logger: Logger = get_system_logger(__name__)
        self.stats_manager: StatsManager = StatsManager(self.settings.stats_file_path)
        self.user_loggers: Dict[str, Logger] = {}

        # Initialize authentication components
        self.auth_manager: AuthManager = auth_manager or AuthManager()
        self.auth_middleware: AuthMiddleware = auth_middleware or AuthMiddleware(self.auth_manager)

        # Initialize Bot Framework Adapter
        self.adapter: BotFrameworkAdapter = self._create_adapter()

        # Initialize Memory Manager
        self.memory_manager: MemoryManager = MemoryManager()

        # Initialize handler registry
        self.handler_registry: HandlerRegistry = HandlerRegistry()
        self._register_default_handlers()

        # Check vector stores
        if not self._check_vector_store(self.settings.openai_vector_store_id_sgc):
            self.handler_registry.disable_handler("sgc")

        if not self._check_vector_store(self.settings.openai_vector_store_id_ref):
            self.handler_registry.disable_handler("ref")
        
        self.system_logger.info("MSBot initialized successfully")

    def _create_adapter(self) -> BotFrameworkAdapter:
        """
        Creates and configures the Bot Framework Adapter.

        This method initializes the adapter with application settings and
        configures a global error handler to catch and log exceptions during
        turn processing.

        Returns:
            BotFrameworkAdapter: The configured adapter instance.
        """
        
        # Bot Framework Adapter Settings
        settings = BotFrameworkAdapterSettings(
            app_id=self.settings.app_id,
            app_password=self.settings.app_password
        )
        # Create adapter
        adapter = BotFrameworkAdapter(settings)
        
        # Error handler
        async def on_error(context: TurnContext, error: Exception):
            traceback.print_exc()

            self.system_logger.error(f"Bot error: {str(error)}")
            # Message when an error occurs
            await context.send_activity(
                MessageFactory.text("Lo siento, ocurrió un error procesando tu mensaje.")
            )
        
        adapter.on_turn_error = on_error
        
        return adapter
    
    async def process_activity(self, body: dict, auth_header: str) -> None:
        """
        Processes an incoming activity from the Bot Framework Connector.

        This method deserializes the incoming request body into an Activity
        object and delegates the processing to the configured adapter.

        Args:
            body (dict): The request body containing the activity data.
            auth_header (str): The authentication header from the request.
        """
        activity = Activity().deserialize(body)
        return await self.adapter.process_activity(activity, auth_header, self.on_turn)

    
    def _register_default_handlers(self) -> None:
        """
        Registers default message handlers with the handler registry.

        This method initializes and registers the AdminHandler, LLMHandler,
        SGCHandler, REFHandler and EchoHandler. It also designates the LLMHandler as
        the default fallback handler.
        """
        # Register RAG Handler (SGC)
        sgc_handler = RAGHandler(
            self.auth_manager,
            self.auth_middleware,
            self.settings.openai_vector_store_id_sgc,
            self._hanlder_map["sgc"]["prefix"],
            Permission(self._hanlder_map["sgc"]["permission"]),
            self._hanlder_map["sgc"]["name"],
            self._hanlder_map["sgc"]["description"],
            self.stats_manager,
            self.memory_manager,
            str(Path(self.settings.templates_dir) / "rag"),
            "_instructions_sgc.txt"
            )
        self.handler_registry.register_handler(self._hanlder_map["sgc"]["name"], sgc_handler, is_default=True)
        self._hanlder_map["sgc"]["instance"] = sgc_handler

        # Register RAG Handler (REF)
        ref_handler = RAGHandler(
            self.auth_manager,
            self.auth_middleware,
            self.settings.openai_vector_store_id_ref,
            self._hanlder_map["ref"]["prefix"],
            Permission(self._hanlder_map["ref"]["permission"]),
            self._hanlder_map["ref"]["name"],
            self._hanlder_map["ref"]["description"],
            self.stats_manager,
            self.memory_manager,
            str(Path(self.settings.templates_dir) / "rag"),
            "_instructions_ref.txt"
            )
        self.handler_registry.register_handler(self._hanlder_map["ref"]["name"], ref_handler, is_default=False)
        self._hanlder_map["ref"]["instance"] = ref_handler

        # Register LLM Handler
        llm_handler = LLMHandler(
            self.auth_manager,
            self.auth_middleware,
            self._hanlder_map["llm"]["prefix"],
            Permission(self._hanlder_map["llm"]["permission"]),
            self._hanlder_map["llm"]["name"],
            self._hanlder_map["llm"]["description"],
            self.stats_manager,
            self.memory_manager,
            str(Path(self.settings.templates_dir) / "llm")
            )
        self.handler_registry.register_handler(self._hanlder_map["llm"]["name"], llm_handler, is_default=False)
        self._hanlder_map["llm"]["instance"] = llm_handler

        # Register Admin Handler
        admin_handler = AdminHandler(
            self.auth_manager,
            self.auth_middleware,
            self._hanlder_map["admin"]["prefix"],
            Permission(self._hanlder_map["admin"]["permission"]),
            self._hanlder_map["admin"]["name"],
            self._hanlder_map["admin"]["description"],
            )
        self.handler_registry.register_handler(self._hanlder_map["admin"]["name"], admin_handler, is_default=False)
        self._hanlder_map["admin"]["instance"] = admin_handler

        # Register File Handler
        file_handler = FileHandler(
            self.auth_manager,
            self.auth_middleware,
            self._hanlder_map["file"]["prefix"],
            Permission(self._hanlder_map["file"]["permission"]),
            self._hanlder_map["file"]["name"],
            self._hanlder_map["file"]["description"],
            self.stats_manager,
            )
        self.handler_registry.register_handler(self._hanlder_map["file"]["name"], file_handler, is_default=False)
        self._hanlder_map["file"]["instance"] = file_handler

        # Register Echo Handler
        echo_handler = EchoHandler(
            self.auth_middleware,
            self._hanlder_map["echo"]["prefix"],
            Permission(self._hanlder_map["echo"]["permission"]),
            self._hanlder_map["echo"]["name"],
            self._hanlder_map["echo"]["description"],
            )
        self.handler_registry.register_handler(self._hanlder_map["echo"]["name"], echo_handler, is_default=False)
        self._hanlder_map["echo"]["instance"] = echo_handler

        # Register Help Handler
        help_handler = HelpHandler(
            self.auth_manager,
            self.auth_middleware,
            self._hanlder_map,
            self._hanlder_map["help"]["prefix"],
            self._hanlder_map["help"]["name"],
            self._hanlder_map["help"]["description"],
        )
        self._hanlder_map["help"]["instance"] = help_handler
        self.handler_registry.register_handler(self._hanlder_map["help"]["name"], help_handler, is_default=False)

        self.system_logger.info("Authentication-enabled handlers registered")
        
    @staticmethod 
    def _get_user_message(turn_context: TurnContext) -> str:
        """
        Gets the user's message from the turn context.

        Args:
            turn_context (TurnContext): The context for the current turn.

        Returns:
            str: The user's message text.
        """
        user_message = turn_context.activity.text
        return user_message
    
    @staticmethod 
    def _get_user_info(turn_context: TurnContext) -> str:
        """
        Gets the user's ID and name from the turn context.

        Args:
            turn_context (TurnContext): The context for the current turn.

        Returns:
            tuple[str, str]: A tuple containing the user's ID and name.
        """
        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name
        return user_id, user_name
    
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """
        Handles incoming message activities from Teams.

        This method serves as the main message processor. It logs the incoming
        message, routes it to the appropriate handler, and sends the response
        back to the user. It also includes error handling for message processing.

        Args:
            turn_context (TurnContext): The context for the current turn.
        """
        user_logger = self._get_user_logger(turn_context)
        _, user_name = self._get_user_info(turn_context)
        self.system_logger.info(f"New message from {user_name}")
        message: str = self._get_user_message(turn_context)

        try:
            
            user_logger.info(f"USER: {message}")

            if message.strip().lower() == "/clear":
                start_time = time.time()
                user_info = self.auth_middleware.get_user_info(turn_context)
                if user_info:
                    response = await self._clear_user_memory(user_info)
                    await turn_context.send_activity(MessageFactory.text(response))
                    delta_time = time.time() - start_time
                    return
                else:
                    await turn_context.send_activity(MessageFactory.text("No se pudo identificar al usuario para borrar el historial."))
                    delta_time = time.time() - start_time
                    return
                
            handler : BaseHandler = self._route_message_to_handler(turn_context)

            if not handler:
                user_logger.error("No hay ningún handler disponible.")
                self.system_logger.error("No handler available")
                await turn_context.send_activity(
                    MessageFactory.text("Lo siento, no puedo procesar tu mensaje. Por favor, inténtalo de nuevo más tarde.")
                )
                return
            
            start_time = time.time()
            response = await handler.handle_message(turn_context)
            delta_time = time.time() - start_time

            if response:
                if isinstance(response, Attachment):
                    user_logger.info("BOT: [Attachment]")
                    message_activity = MessageFactory.attachment(response)
                    await turn_context.send_activity(message_activity)
                elif isinstance(response, str):
                    user_logger.info(f"BOT: {response}")
                    await turn_context.send_activity(MessageFactory.text(response))
                else:
                    user_logger.warning("BOT: [Unexpected Type]")
                    self.system_logger.warning(f"Handler returned unexpected type: {type(response)}")
                    await turn_context.send_activity(
                        MessageFactory.text("Se produjo un error al procesar tu solicitud. Por favor, inténtalo de nuevo más tarde.")
                    )
            else:
                user_logger.warning(f"BOT: [EMPTY]")
                await turn_context.send_activity(
                    MessageFactory.text("No se pudo obtener una respuesta válida. Inténtalo de nuevo.")
                )
        except Exception as e:
            user_logger.error(f"BOT: [ERROR]")
            self.system_logger.error(
                f"General error in on_message_activity: {e}", 
                exc_info=True
            )
            await turn_context.send_activity(
                MessageFactory.text("Lo siento, ocurrió un error inesperado. Nuestro equipo técnico ha sido notificado.")
            )
        finally:
            self.system_logger.info(f"Processing time for {user_name} request: {delta_time:.2f} seconds.")
    
    async def on_members_added_activity(self, members_added: list[ChannelAccount], turn_context: TurnContext) -> None:
        """
        Handles activities when new members are added to the conversation.

        A welcome message is sent to each new member who is not the bot itself.

        Args:
            members_added (list[ChannelAccount]): A list of members who have been added.
            turn_context (TurnContext): The context for the current turn.
        """
        is_authorized, error_msg = await self.auth_middleware.process_message(turn_context)

        if not is_authorized:
            return error_msg
        
        user_info = self.auth_middleware.get_user_info(turn_context)

        user_name = user_info["name"] if user_info else "USER"
        user_role = user_info["role"] if user_info else "ROLE"
        user_permissions = user_info["permissions"] if user_info else []

        sections: List = []

        for _, handler_info in self._hanlder_map.items():
            handler_permission = handler_info.get("permission")
            handler_name = handler_info.get("name")

            if handler_name in ["help", "echo"]:
                continue
            
            if handler_permission is None or handler_permission in user_permissions:
                handler_prefix: str = handler_info.get("prefix")
                handler_instance: BaseHandler = handler_info.get("instance")
                handler_metadata: Dict = handler_info.get("metadata", {}) 
            
                help_data: Dict = handler_instance.get_help() if handler_instance else {}

                functionalities_list: List = handler_metadata.get("functionality", help_data.get('functionality', []))

                section = f"**/{handler_prefix}**\n\n"
                if functionalities_list:
                    functionalities = "\n".join([f"- {func}" for func in functionalities_list])
                    section += f"\n{functionalities}\n\n"

                sections.append(section)

        bot_commands: str = "\n\n".join(sections)

        welcome_text = self._welcome_template.format(
            user_name=user_name,
            user_role=user_role,
            bot_commands= bot_commands
        )

        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(welcome_text)

    def _route_message_to_handler(self, turn_context: TurnContext) -> Optional[Any]:
        """
        Routes an incoming message to the appropriate handler based on its content.

        The method checks the message prefix for specific commands like '/admin',
        '/echo', '/sgc', '/ref' or '/llm' to select a dedicated handler. If no specific
        command is found, it defaults to the pre-configured default handler.

        Args:
            turn_context (TurnContext): The context for the current turn.

        Returns:
            Optional[Any]: The handler instance that can process the message, or None
                         if no handler is available.
        """
        message = self._get_user_message(turn_context)
        # Check for admin commands first
        if message.strip().startswith("/admin"):
            admin_handler = self.handler_registry.get_handler("admin")
            if admin_handler and admin_handler.can_handle(message) and admin_handler.enabled:
                self.system_logger.debug("Route to admin handler")
                return admin_handler
            
        # Use echo handler
        if message.strip().startswith("/echo"):
            echo_handler = self.handler_registry.get_handler("echo")
            if echo_handler and echo_handler.can_handle(message) and echo_handler.enabled:
                self.system_logger.debug("Route to echo handler")
                return echo_handler

        # Use file handler
        if message.strip().startswith("/file"):
            file_handler = self.handler_registry.get_handler("file")
            if file_handler and file_handler.can_handle(message) and file_handler.enabled:
                self.system_logger.debug("Route to file handler")
                return file_handler
            
        # Use SGC handler
        if message.strip().startswith("/sgc"):
            sgc_handler = self.handler_registry.get_handler("sgc")
            if sgc_handler and sgc_handler.can_handle(message) and sgc_handler.enabled:
                self.system_logger.debug("Route to sgc handler")
                return sgc_handler
            
        # Use REF handler
        if message.strip().startswith("/ref"):
            ref_handler = self.handler_registry.get_handler("ref")
            if ref_handler and ref_handler.can_handle(message) and ref_handler.enabled:
                self.system_logger.debug("Route to ref handler")
                return ref_handler
         
        # Use llm handler
        if message.strip().startswith("/llm"):
            llm_handler = self.handler_registry.get_handler("llm")
            if llm_handler and llm_handler.can_handle(message) and llm_handler.enabled:
                self.system_logger.debug("Route to llm handler")
                return llm_handler
        
        # Use help handler
        if message.strip().startswith("/help"):
            help_handler = self.handler_registry.get_handler("help")
            if help_handler and help_handler.can_handle(message) and help_handler.enabled:
                self.system_logger.debug("Route to help handler")
                return help_handler
            
        # Fallback to default handler
        self.system_logger.debug("Route to default handler")
        return self.handler_registry.get_default_handler()

    async def _clear_user_memory(self, user_info: dict) -> str:
        """
        Clears the conversation memory for a specific user.

        Args:
            user_info (dict): The user's information, including 'user_id'.

        Returns:
            str: A confirmation message.
        """
        user_id = user_info.get('user_id')
        user_name = user_info.get('name')
        if user_id:
            self.memory_manager.clear_history_for_user(user_id)
            self.system_logger.info(f"Conversation memory cleared for user: {user_name}")
            return "Historial de conversaciones borrado."
        
        self.system_logger.info(f"Attempted to clear memory for user {user_name}, but no history was found.")
        return "No hay historial de conversaciones para borrar."
    
    def _check_assistant(self, openai_assistant_id: str, verbose: bool = False) -> bool:
        """
        Verifies whether an OpenAI Assistant exists by its ID.

        Logs an informational message if the assistant is found, or a warning if not.

        Args:
            openai_assistant_id (str): The unique ID of the OpenAI Assistant.
            verbose (bool): If True, logs status messages to the system logger.
                        Defaults to False.

        Returns:
            bool: True if the assistant exists, False otherwise.
        """
        assistant = check_assistant_by_id(openai_assistant_id, self.settings.openai_api_key)
        if assistant:
            if verbose:
                self.system_logger.info(f"Assistant found: {assistant.name}")
            return True
        else:
            if verbose:
                self.system_logger.warning(f"Assistant not found with ID: {openai_assistant_id}.")
            return False

    def _check_vector_store(self, openai_vector_store_id: str, verbose: bool = False) -> bool:
        """
        Verifies whether an OpenAI Vector Store exists by its ID.

        Logs an informational message if the vector store is found, or a warning if not.

        Args:
            openai_vector_store_id (str): The unique ID of the OpenAI Vector Store.
            verbose (bool): If True, logs status messages to the system logger.
                        Defaults to False.

        Returns:
            bool: True if the vector store exists, False otherwise.
        """
        vector_store = check_vector_store_by_id(openai_vector_store_id, self.settings.openai_api_key)
        if vector_store:
            if verbose:
                self.system_logger.info(f"Vector Store found: {vector_store.name}")
            return True
        else:
            if verbose:
                self.system_logger.warning(f"Vector Store not found with ID: {openai_vector_store_id}.")
            return False
        
    def _get_user_logger(self, turn_context: TurnContext) -> Logger:
        """
        Gets or creates a logger instance specific to the user.

        This method ensures that each user has a dedicated logger for
        recording their conversation interactions.

        Args:
            turn_context (TurnContext): The context for the conversation.

        Returns:
            Logger: The logger instance configured for the user.
        """
        user_id, user_name = self._get_user_info(turn_context)
        user_id = user_id.split(':')[1]
        if not user_id or not user_name:
            return self.system_logger

        if user_id not in self.user_loggers:
            self.user_loggers[user_id] = get_user_logger(user_id, user_name)

        return self.user_loggers[user_id]