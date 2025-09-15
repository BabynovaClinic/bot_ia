from typing import Any, List, Optional, Dict
from langchain.schema import BaseMessage, AIMessage, ChatResult, ChatGeneration
from langchain.chat_models.base import BaseChatModel
from langchain.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.runnables import RunnableBinding

from src.open_ai.client import OpenAIClient

class OpenAIChatWrapper(BaseChatModel):
    """
    LangChain-compatible wrapper for OpenAIClient with dynamic parameter overrides.

    This class provides a seamless integration between the custom OpenAIClient
    and the LangChain framework. It adapts LangChain's message and generation
    formats to work with the OpenAIClient's methods, supporting both
    synchronous and asynchronous operations. The wrapper allows for dynamic
    overrides of tools and attachments on a per-call basis while maintaining
    default configurations.

    Attributes:
        client: OpenAIClient: An instance of the OpenAIClient used for API calls.
        streaming: bool: A boolean indicating whether to use streaming
                         for responses.
        default_tools: List[Dict[str, Any]]: A list of default tool
                                             configurations.
        default_attachments: List[Dict[str, Any]]: A list of default
                                                   attachment configurations.
    """

    client: OpenAIClient
    streaming: bool = False
    default_tools: List[Dict[str, Any]] = []
    default_attachments: List[Dict[str, Any]] = []

    def __init__(
        self,
        client: Any,
        streaming: bool = False,
        default_tools: List[Dict[str, Any]] = [],
        default_attachments: List[Dict[str, Any]] = [],
        **kwargs
    ):
        """
        Initializes the OpenAIChatWrapper.
        
        Args:
            client: An instance of the OpenAIClient.
            streaming: If True, uses streaming for API responses.
            default_tools: A list of default tool configurations.
            default_attachments: A list of default attachment configurations.
        """
        super().__init__(
            client=client,
            streaming=streaming,
            default_tools=default_tools,
            default_attachments=default_attachments,
            **kwargs
        )

    @property
    def _llm_type(self) -> str:
        """
        Returns the type of the LLM wrapper.
        
        Returns:
            str: The string "openai-chat-wrapper".
        """
        return "openai-chat-wrapper"
    
    def _convert_messages_to_dict(self, messages: List[BaseMessage]) -> List[dict]:
        """
        Converts a list of LangChain BaseMessage objects to a list of dictionaries
        formatted for the OpenAIClient.

        This internal helper method maps LangChain's message types (e.g., "human",
        "ai") to the standard OpenAI roles ("user", "assistant").

        Args:
            messages (List[BaseMessage]): A list of LangChain message objects.

        Returns:
            List[dict]: A list of dictionaries with "role" and "content" keys.
        """
        role_map = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}
        return [{"role": role_map.get(msg.type, "user"), "content": msg.content} for msg in messages]

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> RunnableBinding:
        """
        Bind tools to the model.

        Args:
            tools (List[Any]): A list of tools to bind to the LLM.
            **kwargs (Any): Additional parameters.

        Returns:
            RunnableBinding: A new runnable with the tools bound.
        """
        return self.bind(tools=tools, **kwargs)
    
    def _generate(
        self,
        messages: List[BaseMessage],
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Generates a synchronous chat response based on a list of messages.

        This method orchestrates the call to the underlying OpenAIClient,
        handling message conversion, tool and attachment overrides, and
        either a standard or streaming invocation based on the `streaming`
        attribute.

        Args:
            messages (List[BaseMessage]): A list of messages representing the
                                          conversation history.
            run_manager (Optional[CallbackManagerForLLMRun]): Callback manager
                                                              for handling
                                                              streaming events.
            **kwargs (Any): Additional parameters for the API call, which can
                            override `default_tools` and `default_attachments`.

        Returns:
            ChatResult: An object containing the generated response.
        """
        formatted_messages = self._convert_messages_to_dict(messages)

        tools = kwargs.get("tools", []) + self.default_tools
        attachments = kwargs.get("attachments", []) + self.default_attachments

        kwargs.pop("stop", None)
        kwargs.pop("tools", None)
        kwargs.pop("attachments", None)

        if self.streaming:
            text_chunks = []
            for chunk in self.client.stream_invoke(
                formatted_messages,
                extra_tools=tools,
                attachments=attachments,
                **kwargs
            ):
                text_chunks.append(chunk)
                if run_manager:
                    run_manager.on_llm_new_token(chunk)
            final_text = "".join(text_chunks)
        else:
            final_text, _ = self.client.invoke(
                formatted_messages,
                extra_tools=tools,
                attachments=attachments,
                **kwargs
            )

        generation = ChatGeneration(message=AIMessage(content=final_text))
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Generates an asynchronous chat response based on a list of messages.

        This non-blocking method calls the asynchronous invocation methods of
        the OpenAIClient, suitable for applications that need to process
        multiple requests concurrently. It handles message conversion and
        passes along tools, attachments, and other keyword arguments.

        Args:
            messages (List[BaseMessage]): A list of messages representing the
                                          conversation history.
            run_manager (Optional[AsyncCallbackManagerForLLMRun]): Callback
                                                                  manager for
                                                                  handling
                                                                  asynchronous
                                                                  streaming
                                                                  events.
            **kwargs (Any): Additional parameters for the API call, which can
                            override `default_tools` and `default_attachments`.

        Returns:
            ChatResult: An object containing the generated response.
        """
        formatted_messages = self._convert_messages_to_dict(messages)

        tools = kwargs.get("tools", []) + self.default_tools
        attachments = kwargs.get("attachments", []) + self.default_attachments

        kwargs.pop("stop", None)
        kwargs.pop("tools", None)
        kwargs.pop("attachments", None)
        
        if self.streaming:
            text_chunks = []
            async for chunk in self.client.astream_invoke(
                formatted_messages,
                extra_tools=tools,
                attachments=attachments,
                **kwargs
            ):
                text_chunks.append(chunk)
                if run_manager:
                    await run_manager.on_llm_new_token(chunk)
            final_text = "".join(text_chunks)
        else:
            final_text, _ = await self.client.ainvoke(
                formatted_messages,
                extra_tools=tools,
                attachments=attachments,
                **kwargs
            )

        generation = ChatGeneration(message=AIMessage(content=final_text))
        return ChatResult(generations=[generation])