from typing import Any, Callable, Dict, Optional, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import Runnable
from src.lang_chain.open_ai_chat_wrapper import OpenAIChatWrapper
from langchain.schema import BaseMessage

class OpenAIChatRunnable:
    """
    Runnable wrapper that executes a chain: ChatPromptTemplate (with MessagesPlaceholder)
    -> OpenAIChatWrapper (with tools bound) and is wrapped by RunnableWithMessageHistory.

    This class sets up a LangChain `Runnable` for an OpenAI chat model,
    integrating conversation history and tool-calling capabilities. It ensures that
    tools are properly bound to the language model, allowing it to make function
    calls based on user input.

    Attributes:
        llm (OpenAIChatWrapper): The wrapped OpenAI chat model instance.
        tools (List[Dict[str, Any]]): The list of tool definitions provided to the LLM.
        history_getter (Callable): A function to retrieve conversation history.
        prompt (ChatPromptTemplate): The prompt template used to format messages.
        runnable (RunnableWithMessageHistory): The complete runnable chain,
                                                including history and tool-bound LLM.
    """
    def __init__(
        self,
        llm: OpenAIChatWrapper,
        history_getter: Callable[[Dict[str, Any], Dict[str, Any]], Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instructions: Optional[str] = None,
        ):
        """
        Initializes the OpenAIChatRunnable with the LLM, history, and tools.

        Args:
            llm (OpenAIChatWrapper): The LLM wrapper instance.
            history_getter (Callable): A callable to get a message history instance
                                        for a given session.
            tools (Optional[List[Dict[str, Any]]]): A list of tool definitions to
                                                    bind to the LLM. Defaults to None.
            system_instructions (Optional[str]): System-level instructions to guide
                                                the LLM's behavior. Defaults to
                                                "You are a helpful assistant."
        """
        self.llm = llm
        self.tools = tools or []
        self.history_getter = history_getter

        system_text = system_instructions or "You are a helpful assistant."
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_text),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])

        core: Runnable = self.prompt | self.llm.bind_tools(self.tools)  

        self.runnable = RunnableWithMessageHistory(
            core,
            history_getter,
            input_messages_key="input",
            history_messages_key="chat_history"
        )

    async def ainvoke(self, message: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Asynchronously invokes the runnable with the user's message.

        Args:
            message (str): The user's input message.
            config (Optional[Dict[str, Any]]): A configuration dictionary, typically
                                                used to pass the session ID for history.

        Returns:
            Dict[str, Any]: A dictionary containing the LLM's response. The response
                            is a Message object, not a plain string.
        """
        result = await self.runnable.ainvoke(
            {"input": message},
            config=config or {},
        )
        return {"response": getattr(result, "content", result)}

    def invoke(self, message: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Synchronously invokes the runnable with the user's message.

        Args:
            message (str): The user's input message.
            config (Optional[Dict[str, Any]]): A configuration dictionary, typically
                                                used to pass the session ID for history.

        Returns:
            Dict[str, Any]: A dictionary containing the LLM's response. The response
                            is a Message object, not a plain string.
        """
        result = self.runnable.invoke(
            {"input": message},
            config=config or {},
        )
        return {"response": getattr(result, "content", result)}
