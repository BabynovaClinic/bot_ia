import os

def load_txt(path:str):
    """
    Loads the content of a .txt file as a single string.

    This function reads a text file from the specified path, performing several checks
    to ensure the file exists and has the correct extension. The entire content of the
    file is read into a single string.

    Args:
        path (str): The full path to the .txt file.

    Returns:
        str: The content of the .txt file as a single string.

    Raises:
        TypeError: If the provided path is not a string.
        FileNotFoundError: If the file does not exist at the specified path.
        ValueError: If the file does not have a .txt extension.
    """
    if not isinstance(path, str):
        raise TypeError("path must be a string.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"The file '{path}' does not exist.")
    if not path.lower().endswith(".txt"):
        raise ValueError("The file must have the extension .txt")
    
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
        return content