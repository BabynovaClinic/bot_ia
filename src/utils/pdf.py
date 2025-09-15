import os
import subprocess
from typing import Optional, List

from src.log.system_logger import Logger, get_system_logger
from src.config.settings import Settings, get_settings

LOG: Logger = get_system_logger(__name__)
SETTINGS: Settings = get_settings()

def convert_to_pdf(input_path: str, output_path: str, libreoffice_path: str = SETTINGS.libreoffice_path) -> Optional[str]:
    """
    Converts a file from an input path to a PDF on an output path.

    Args:
        input_path (str): The full path to the file to be converted.
        output_path (str): The full path where the PDF file will be saved.
        libreoffice_path (str): The path to the LibreOffice executable (soffice.exe). If not provided, the default setting will be used.

    Returns:
        Optional[str]: The path to the PDF file if the conversion was successful, otherwise None.
    """
    supported_extensions: List[str] = ['doc', 'docx', 'xlsx', 'xls', 'ods', 'odt', 'ppt', 'pptx']

    file_extension = os.path.splitext(input_path)[1].lstrip('.').lower()

    if file_extension not in supported_extensions:
        if file_extension == 'pdf':
            LOG.warning("The input file is already a PDF. No conversion needed.")
            return input_path
        else:
            LOG.error(f"File extension '{file_extension}' is not supported for PDF conversion.")
            return None

    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        subprocess.run(
            [libreoffice_path, '--headless', '--convert-to', 'pdf', '--outdir', output_dir, input_path],
            check=True,
            timeout=30
        )
        
        generated_pdf_path : str = os.path.join(output_dir, os.path.splitext(os.path.basename(input_path))[0] + ".pdf")
        
        if os.path.exists(generated_pdf_path):
            os.rename(generated_pdf_path, output_path)
            LOG.debug(f"PDF file generated at: {output_path}")
            return output_path
        else:
            LOG.error("LibreOffice could not generate the PDF file.")
            return None

    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        LOG.error(f"Error during conversion: {e}")
        return None