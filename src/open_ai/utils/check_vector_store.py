from openai import OpenAI
from openai import NotFoundError

def check_vector_store_by_id(vector_store_id: str, api_key: str):
    """
    Checks if a vector store exists in OpenAI using its ID.

    Args:
        vector_store_id (str): ID of the vector store to verify.
        api_key (str): Your OpenAI API key.
    
    Returns:
        The VectorStore object if found.
        None: If the vector store is not found or an error occurs.
    """
    try:
        client = OpenAI(api_key=api_key)
        vector_store = client.vector_stores.retrieve(vector_store_id)
        return vector_store

    except NotFoundError:
        return None

    except Exception:
        return None