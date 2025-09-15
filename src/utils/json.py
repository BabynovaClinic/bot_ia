import os
import json
from typing import Dict, Any

from src.log.system_logger import Logger, get_system_logger

LOG: Logger = get_system_logger(__name__)

def load_json(file_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Loads a dictionary from a JSON file.

    This function safely attempts to read and parse a JSON file. If the file does not exist,
    is not a valid JSON, or an unexpected error occurs, it handles the exception gracefully
    and returns an empty dictionary.

    Args:
        file_path (str): The full path to the JSON file to be loaded.

    Returns:
        Dict[str, Dict[str, Any]]: A dictionary containing the loaded data from the JSON file,
        or an empty dictionary if the file cannot be loaded.
    """
    if not os.path.exists(file_path):
        LOG.warning(f"Local file not found at '{file_path}'. Creating a new empty one.")
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            LOG.debug(f"Loaded {len(data)} entries from '{file_path}'.")
            return data
    except json.JSONDecodeError as e:
        LOG.error(f"Error decoding JSON from '{file_path}': {e}. Starting with an empty record.")
        return {}
    except Exception as e:
        LOG.error(f"An unexpected error occurred while loading '{file_path}': {e}. Starting with an empty record.")
        return {}

def save_json(file_path: str, data: Dict[str, Dict[str, Any]]) -> None:
    """
    Saves a dictionary to a JSON file, ensuring the directory exists beforehand.

    This function writes the provided dictionary to a JSON file with a formatted, human-readable
    indentation. It creates the parent directory if it does not already exist,
    preventing `FileNotFoundError` during the save operation.

    Args:
        file_path (str): The full path to the JSON file where the data will be saved.
        data (Dict[str, Dict[str, Any]]): The dictionary to be saved.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        LOG.debug(f"Saved {len(data)} entries to '{file_path}'.")
    except Exception as e:
        LOG.error(f"Error saving file to '{file_path}': {e}")
        pass