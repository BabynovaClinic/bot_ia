import openai
from typing import Any, Dict, List, Optional, Tuple, Union, Iterator, AsyncIterator

class OpenAIClient:
    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        instructions: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        ) -> None:
        """
        Handles interactions with the OpenAI API for generating and managing responses.

        This class provides a unified interface for various API functionalities, including
        synchronous and asynchronous calls, streaming, and tool integration. It simplifies
        the process of sending messages and receiving structured responses while managing
        configuration settings like the model, temperature, and output token limits.

        Features:
            - Synchronous and asynchronous requests: Supports both blocking (`invoke`) and non-blocking (`ainvoke`) calls.
            - Response streaming: Enables real-time reception of responses with `stream_invoke` and `astream_invoke`.
            - Dynamic tool integration: Manages predefined tools during initialization and allows for additional tools per request.
            - Context building: Formats and validates message history to ensure consistency with API requirements.
            - Configurable parameters: Allows customization of model, temperature, and token limits.
            - Helper functions for tools and attachments: Simplifies the creation of common tool and attachment configurations (e.g., file search, web search, code interpreter).

        Attributes:
            api_key (Optional[str]): The API key for authentication with OpenAI.
            model (str): The name of the language model to be used.
            instructions (Optional[str]): Initial instructions for the model's behavior.
            tools (Optional[List[Dict[str, Any]]]): A list of predefined tools the model can use.
            temperature (Optional[float]): Controls the randomness of the model's output.
            max_output_tokens (Optional[int]): The maximum number of tokens to generate
                                            in the response.
        """
        self.api_key = api_key
        self.model = model
        self.instructions = instructions
        self.tools = tools or []
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        self._client = openai.OpenAI(api_key=self.api_key) if api_key else openai.OpenAI()
        self._aclient = openai.AsyncOpenAI(api_key=self.api_key) if api_key else openai.AsyncOpenAI()

    # -------------------- Context builder --------------------
    @staticmethod
    def build_context(
        messages: List[Union[Dict[str, str], Tuple[str, str]]]
        ) -> List[Dict[str, str]]:
        """
        Builds and validates a list of messages with standard role formatting.

        This static method takes a list of messages, either as dictionaries or tuples,
        and ensures they are correctly formatted with a "role" and "content" key.
        It validates that the roles are standard ("system", "user", "assistant", "tool")
        before returning the formatted list. This is crucial for maintaining a
        consistent conversation history for the API.

        Args:
            messages (List[Union[Dict[str, str], Tuple[str, str]]]): A list of messages in dictionary or tuple format.

        Returns:
            List[Dict[str, str]]: A list of validated messages formatted as dictionaries.

        Raises:
            ValueError: If an invalid role is found.
            TypeError: If the input list does not contain dictionaries or tuples.
        """
        valid_roles = {"system", "user", "assistant", "tool"}
        context = []
        
        first_item = messages[0]
        if isinstance(first_item, dict):
            for item in messages:
                role = item.get("role")
                content = item.get("content")
                if role not in valid_roles:
                    raise ValueError(f"Invalid role found: '{role}'. Allowed roles are {valid_roles}.")
                context.append({"role": role, "content": content})
                
        elif isinstance(first_item, tuple):
            for role, content in messages:
                if role not in valid_roles:
                    raise ValueError(f"Invalid role found: '{role}'. Allowed roles are {valid_roles}.")
                context.append({"role": role, "content": content})
        
        else:
            raise TypeError("The history format must be a list of dictionaries or tuples.")

        return context

    def _build_kwargs(
        self,
        user_input: Union[str, List[Dict[str, Any]]],
        attachments: Optional[List[Dict[str, Any]]] = None,
        extra_tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
        ) -> Dict[str, Any]:
        """
        Builds the keyword arguments dictionary for the OpenAI API call.

        This internal helper method constructs the request payload,
        including the model, input, instructions, tools, attachments, and
        other configurable parameters. It supports both explicit parameters
        and arbitrary keyword arguments for future API compatibility.

        Args:
            user_input (Union[str, List[Dict[str, Any]]]): 
                The user's input message or the full message history.
            attachments (Optional[List[Dict[str, Any]]]): 
                Files or other attachments to be included in the request.
            extra_tools (Optional[List[Dict[str, Any]]]): 
                Additional tools to be used for the current request.
            tool_choice (Optional[str]): 
                Specifies how tools should be selected during the request.
                - None: default if no tools are present.
                - "auto": default if tools are present.
                - Other values may specify a particular tool.
            temperature (Optional[float]): 
                Sampling temperature (0–2). Higher values produce more random outputs.
            max_output_tokens (Optional[int]): 
                Maximum number of tokens to generate in the response.
            metadata (Optional[Dict[str, str]]): 
                Custom metadata for tracing, logging, or contextual information.
            **kwargs (Any): 
                Additional API parameters passed directly through (e.g., top_p, 
                presence_penalty, frequency_penalty, stop, response_format, logprobs).

        Returns:
            Dict[str, Any]: A dictionary of keyword arguments formatted for the
                            OpenAI API's `create` method.
        """
        kwargs_out: Dict[str, Any] = {
            "model": self.model,
            "input": user_input,
        }

        if self.instructions:
            kwargs_out["instructions"] = self.instructions

        if self.tools or extra_tools:
            kwargs_out["tools"] = [*self.tools, *(extra_tools or [])]
            if tool_choice is None:
                kwargs_out["tool_choice"] = "auto"
            else:
                kwargs_out["tool_choice"] = tool_choice
        elif tool_choice is not None:
            kwargs_out["tool_choice"] = tool_choice

        if attachments:
            kwargs_out["attachments"] = attachments

        if temperature is not None:
            kwargs_out["temperature"] = temperature
        elif self.temperature is not None:
            kwargs_out["temperature"] = self.temperature

        if max_output_tokens is not None:
            kwargs_out["max_output_tokens"] = max_output_tokens
        elif self.max_output_tokens is not None:
            kwargs_out["max_output_tokens"] = self.max_output_tokens

        if metadata:
            kwargs_out["metadata"] = metadata

        kwargs_out.update(kwargs)

        return kwargs_out

    def _extract_text(
        self,
        response: Any
        ) -> str:
        """
        Extracts the text content from an OpenAI API response object.

        This helper method abstracts the process of navigating the nested
        response structure to find the final text output, ensuring compatibility
        with different response formats.

        Args:
            response (Any): The response object returned by the OpenAI API.

        Returns:
            str: The extracted text content from the response. Returns an empty string
                 if no text is found.
        """
        if hasattr(response, "output_text"):
            return response.output_text or ""
        pieces: List[str] = []
        for item in getattr(response, "output", []) or []:
            for c in getattr(item, "content", []) or []:
                if hasattr(c, "text") and isinstance(c.text, str):
                    pieces.append(c.text)
        return "".join(pieces)

    # ------------------ Métodos principales ------------------
    def invoke(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        attachments: Optional[List[Dict[str, Any]]] = None,
        extra_tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
        ) -> Tuple[str, Any]:
        """
        Sends a synchronous request to the OpenAI API and retrieves a response.

        This method is a blocking call that sends the user message and any
        additional configurations to the API and waits for the full response. It
        now accepts additional keyword arguments (**kwargs) which are passed directly
        to the underlying API call.

        Args:
            user_message (Union[str, List[Dict[str, Any]]]): The user's input message or a complete conversation history.
            attachments (Optional[List[Dict[str, Any]]]): Files to be included in the request.
            extra_tools (Optional[List[Dict[str, Any]]]): Additional tools for this specific call.
            **kwargs (Any): Additional API parameters (e.g., temperature, max_output_tokens, metadata).

        Returns:
            Tuple[str, Any]: A tuple containing the extracted text of the response
                             and the raw response object from the API.
        """
        kwargs_out = self._build_kwargs(user_message, attachments, extra_tools, **kwargs)
        resp = self._client.responses.create(**kwargs_out)
        return self._extract_text(resp), resp

    async def ainvoke(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        attachments: Optional[List[Dict[str, Any]]] = None,
        extra_tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
        ) -> Tuple[str, Any]:
        """
        Sends an asynchronous request to the OpenAI API and retrieves a response.

        This method is an non-blocking asynchronous call, suitable for applications
        that need to perform other tasks while waiting for the API response. It
        now accepts additional keyword arguments (**kwargs) which are passed directly
        to the underlying API call.

        Args:
            user_message (Union[str, List[Dict[str, Any]]]): The user's input message or a complete conversation history.
            attachments (Optional[List[Dict[str, Any]]]): Files to be included in the request.
            extra_tools (Optional[List[Dict[str, Any]]]): Additional tools for this specific call.
            **kwargs (Any): Additional API parameters (e.g., temperature, max_output_tokens, metadata).

        Returns:
            Tuple[str, Any]: A tuple containing the extracted text of the response
                             and the raw response object from the API.
        """
        kwargs_out = self._build_kwargs(user_message, attachments, extra_tools, **kwargs)
        resp = await self._aclient.responses.create(**kwargs_out)
        return self._extract_text(resp), resp

    def stream_invoke(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        attachments: Optional[List[Dict[str, Any]]] = None,
        extra_tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
        ) -> Iterator[str]:
        """
        Sends a synchronous streaming request to the OpenAI API.

        This method provides a generator that yields parts of the response as
        they are received, allowing for real-time display of the LLM's output. It
        now accepts additional keyword arguments (**kwargs) which are passed directly
        to the underlying API call.

        Args:
            user_message (Union[str, List[Dict[str, Any]]]): The user's input message or a complete conversation history.
            extra_tools (Optional[List[Dict[str, Any]]]): Additional tools for this specific call.
            attachments (Optional[List[Dict[str, Any]]]): Files to be included in the request.
            **kwargs (Any): Additional API parameters (e.g., temperature, max_output_tokens, metadata).

        Returns:
            Iterator[str]: An iterator that yields string chunks of the streamed response.
        """
        kwargs_out = self._build_kwargs(user_message, attachments, extra_tools=extra_tools, **kwargs)
        with self._client.responses.stream(**kwargs_out) as stream:
            for event in stream:
                if event.type == "response.output_text.delta" and hasattr(event, "delta"):
                    yield event.delta

    async def astream_invoke(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        attachments: Optional[List[Dict[str, Any]]] = None,
        extra_tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
        ) -> AsyncIterator[str]:
        """
        Sends an asynchronous streaming request to the OpenAI API.

        This method is an non-blocking asynchronous call that returns an async
        iterator, ideal for web applications or systems that need to handle
        streaming responses without blocking the event loop. It now accepts additional
        keyword arguments (**kwargs) which are passed directly to the underlying API call.

        Args:
            user_message (Union[str, List[Dict[str, Any]]]): The user's input message or a complete conversation history.
            attachments (Optional[List[Dict[str, Any]]]): Files to be included in the request.
            extra_tools (Optional[List[Dict[str, Any]]]): Additional tools for this specific call.
            **kwargs (Any): Additional API parameters (e.g., temperature, max_output_tokens, metadata).

        Returns:
            AsyncIterator[str]: An asynchronous iterator that yields string chunks
                                of the streamed response.
        """
        kwargs_out = self._build_kwargs(user_message, attachments, extra_tools=extra_tools, **kwargs)
        async with self._aclient.responses.stream(**kwargs_out) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta" and hasattr(event, "delta"):
                    yield event.delta

    # ----------------- Helpers para tools y attachments -----------------
    @staticmethod
    def tool_file_search(vector_store_ids: List[str], **opts: Any) -> Dict[str, Any]:
        """
        Creates a tool configuration for file search.

        This helper function generates the dictionary structure required by the
        OpenAI API to enable file search functionality using specified vector stores.

        Args:
            vector_store_ids (List[str]): A list of IDs for the vector stores to search.
            **opts (Any): Additional options for the tool configuration.

        Returns:
            Dict[str, Any]: A dictionary representing the file search tool.
        """
        return {"type": "file_search", "vector_store_ids": vector_store_ids, **opts}

    @staticmethod
    def attachment_file(file_id: str, tool_types: List[str] = ["file_search"]) -> Dict[str, Any]:
        """
        Creates an attachment configuration for a file.

        This helper function generates the dictionary structure for attaching a
        file to an API request, specifying which tools should be used with it.

        Args:
            file_id (str): The ID of the file to be attached.
            tool_types (List[str]): A list of tool types to be applied to the file.

        Returns:
            Dict[str, Any]: A dictionary representing the file attachment.
        """
        return {"file_id": file_id, "tools": [{"type": t} for t in tool_types]}

    @staticmethod
    def tool_web_search(**opts: Any) -> Dict[str, Any]:
        """
        Creates a tool configuration for web search.

        Args:
            **opts (Any): Additional options for the tool configuration.

        Returns:
            Dict[str, Any]: A dictionary representing the web search tool.
        """
        return {"type": "web_search", **opts}

    @staticmethod
    def tool_code_interpreter(**opts: Any) -> Dict[str, Any]:
        """
        Creates a tool configuration for a code interpreter.

        Args:
            **opts (Any): Additional options for the tool configuration.

        Returns:
            Dict[str, Any]: A dictionary representing the code interpreter tool.
        """
        return {"type": "code_interpreter", **opts}

    @staticmethod
    def function_tool(name: str, description: str, parameters_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a tool configuration for a custom function.

        This helper function generates the dictionary structure required by the
        OpenAI API to define a custom function that the model can call.

        Args:
            name (str): The name of the function.
            description (str): A description of the function's purpose.
            parameters_schema (Dict[str, Any]): A JSON schema describing the
                                                 function's parameters.

        Returns:
            Dict[str, Any]: A dictionary representing the custom function tool.
        """
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters_schema,
            },
        }
    