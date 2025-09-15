import asyncio
from langchain.chains.base import Chain
from langchain.schema import HumanMessage
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.manager import CallbackManagerForChainRun, AsyncCallbackManagerForChainRun
from typing import Dict, Any, List, Optional

from src.lang_chain.open_ai_chat_wrapper import OpenAIChatWrapper

class OpenAIChatChain(Chain):
    """
    A custom LangChain for multi-turn conversations with memory and tools.

    This chain extends the base LangChain `Chain` class to manage a conversation
    flow that includes a language model, conversational memory, and a list of
    available tools. It handles the message history, updates the memory with
    each new turn, and passes the context to the underlying LLM for generation.
    It's designed to be flexible, supporting both synchronous and asynchronous
    operations while integrating with LangChain's callback system.

    Attributes:
        llm (OpenAIChatWrapper): The language model wrapper used to interact with
                                 the OpenAI API.
        memory (ConversationBufferMemory): The memory component that stores the
                                           conversation history.
        tools (List[Dict[str, Any]]): A list of tool configurations available
                                      to the language model.
    """

    llm: OpenAIChatWrapper
    memory: ConversationBufferMemory
    tools: List[Dict[str, Any]]

    @property
    def input_keys(self) -> List[str]:
        """
        Defines the keys expected in the input dictionary for the chain.

        Returns:
            List[str]: A list containing the string "input".
        """
        return ["input"]

    @property
    def output_keys(self) -> List[str]:
        """
        Defines the keys included in the output dictionary returned by the chain.

        Returns:
            List[str]: A list containing the string "response".
        """
        return ["response"]

    def _call(
        self, 
        inputs: Dict[str, Any], 
        run_manager: Optional[CallbackManagerForChainRun] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Processes a synchronous request by a user, generates a response, and
        updates the conversation memory.

        This method retrieves the user's input, adds it to the conversation
        history stored in memory, and then invokes the LLM with the full
        message history and tools. Finally, it adds the LLM's response
        to the memory and returns it.

        Args:
            inputs (Dict[str, Any]): The input dictionary containing the user's
                                     message under the "input" key.
            run_manager (Optional[CallbackManagerForChainRun]): A callback
                                                                manager to
                                                                handle events
                                                                during the chain's
                                                                execution.
            **kwargs (Any): Additional parameters to be passed directly to the
                            LLM's `invoke` method.

        Returns:
            Dict[str, Any]: A dictionary containing the LLM's response under
                            the "response" key.
        """
        user_input = inputs["input"]
        messages = self.memory.chat_memory.messages
        messages.append(HumanMessage(content=user_input))

        response_obj = self.llm.invoke(
            messages, 
            stop=inputs.get("stop"),
            tools=self.tools,
            # callbacks=run_manager.get_child() if run_manager else None,
            **kwargs
        )
        
        self.memory.chat_memory.add_ai_message(response_obj)
        return {"response": response_obj.content}
    
    async def _acall(
        self, 
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Processes an asynchronous request by a user, generates a response, and
        updates the conversation memory.

        This asynchronous method works similarly to `_call`, but uses the LLM's
        `ainvoke` method for non-blocking operations. It's suitable for
        concurrent environments where the application needs to perform other tasks
        while waiting for the LLM response.

        Args:
            inputs (Dict[str, Any]): The input dictionary containing the user's
                                     message under the "input" key.
            run_manager (Optional[AsyncCallbackManagerForChainRun]): An
                                                                    asynchronous
                                                                    callback manager.
            **kwargs (Any): Additional parameters to be passed directly to the
                            LLM's `ainvoke` method.

        Returns:
            Dict[str, Any]: A dictionary containing the LLM's response under
                            the "response" key.
        """
        user_input = inputs["input"]
        messages = self.memory.chat_memory.messages
        messages.append(HumanMessage(content=user_input))

        response_obj = await self.llm.ainvoke(
            messages,
            stop=inputs.get("stop"),
            tools=self.tools,
            # callbacks=run_manager.get_child() if run_manager else None,
            **kwargs
        )

        self.memory.chat_memory.add_ai_message(response_obj)
        return {"response": response_obj.content}