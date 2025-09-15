import re

def extract_response(text):
    """
    Extracts content enclosed within [RESPONSE] and [/RESPONSE] tags, or
    from [RESPONSE] to the end of the string if the closing tag is absent.

    This function first attempts to find a complete `[RESPONSE]...[/RESPONSE]`
    block. If a complete block is not found, it then looks for an opening
    `[RESPONSE]` tag and extracts all content from that point to the
    end of the string.

    Args:
        text (str): The input string to search.

    Returns:
        str or None: The extracted content, with leading/trailing whitespace
                      removed. Returns None if no `[RESPONSE]` tag is found.
    """
    complete_pattern = r'\[RESPONSE\](.*?)\[/RESPONSE\]'
    partial_pattern = r'\[RESPONSE\](.*)'
    
    match = re.search(complete_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    match = re.search(partial_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    return text