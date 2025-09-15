from openai import OpenAI
from openai import NotFoundError

def check_assistant_by_id(assistant_id: str, api_key: str):
    """
    Checks if an OpenAI assistant exists using its ID.

    Args:
        assistant_id (str): The ID of the assistant to check.
        api_key (str): Your OpenAI API key.

    Returns:
        Assistant: The OpenAI Assistant object if found.
        None: If the assistant is not found or an error occurs.
    """
    try:
        client = OpenAI(api_key=api_key)
        assistant = client.beta.assistants.retrieve(assistant_id)
        return assistant
    except NotFoundError:
        return None
    except Exception:
        return None