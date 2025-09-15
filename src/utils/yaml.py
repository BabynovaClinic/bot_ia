import os
import yaml

def load_yaml(path: str):
    """
    Loads and parses the content of a YAML file.

    This function reads a YAML or YML file from the specified path, performing several checks
    to ensure the file exists and has a valid extension. The file's content is then safely
    parsed into a Python object (e.g., a dictionary or list).

    Args:
        path (str): The full path to the YAML file.

    Returns:
        Any: The content of the YAML file, which can be a dictionary, list, or other Python type.

    Raises:
        TypeError: If the provided path is not a string.
        FileNotFoundError: If the file does not exist at the specified path.
        ValueError: If the file does not have a .yaml or .yml extension, or if there is a parsing error.
    """
    if not isinstance(path, str):
        raise TypeError("The 'path' argument must be a string.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"The file '{path}' does not exist.")
    if not path.lower().endswith((".yaml", ".yml")):
        raise ValueError("The file must have a .yaml or .yml extension.")
    
    with open(path, "r", encoding="utf-8") as file:
        try:
            content = yaml.safe_load(file)
            return content
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file '{path}': {e}")