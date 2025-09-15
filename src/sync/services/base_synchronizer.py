import os
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Any
import tempfile

from src.ms_sharepoint.client import SharePointClient
from src.open_ai.vector_store import OpenAIVectorStore
from src.log.system_logger import Logger, get_system_logger
from src.config.settings import Settings, get_settings
from src.utils.json import load_json, save_json
from src.utils.pdf import convert_to_pdf
from src.utils.decorators import retry_on_exception

class BaseFileSynchronizer(ABC):
    """
    Represents a base class for file synchronization between SharePoint and an OpenAI Vector Store.

    This abstract class provides the core logic and structure for managing file synchronization, including
    retrieval, processing, and status tracking, ensuring consistency between a source (SharePoint)
    and a destination (OpenAI Vector Store).

    Features:
        - Initialization of SharePoint and OpenAI clients.
        - Retrieval of relevant files from SharePoint with filtering options.
        - Handling of new and updated files, including format conversion.
        - Management of the synchronization state, tracking new, updated, and stale files.
        - Deletion of files from the OpenAI Vector Store that are no longer in SharePoint.
        - Purge functionality to clear the vector store and local records.

    Attributes:
        settings (Settings): Application settings.
        system_logger (Logger): A logger for recording system and command events.
        sharepoint_client (SharePointClient): Client for interacting with SharePoint.
        vector_store (OpenAIVectorStore): Client for interacting with the OpenAI Vector Store.
        files_data (Dict[str, Dict[str, Any]]): A dictionary to store the synchronization state of files.
        updated_files_data (Dict[str, Dict[str, Any]]): A dictionary to store data for files that have been updated or added during the current run.
        running_sharepoint_file_ids (set): A set of SharePoint file IDs processed in the current synchronization run.
    """
    def __init__(self, vector_store_id: str):
        """
        Initializes the synchronizer with SharePoint and OpenAI Vector Store clients.

        Args:
            vector_store_id (str): The unique ID of the OpenAI Vector Store to be used for synchronization.
        """
        self.settings: Settings = get_settings()
        self.system_logger: Logger = get_system_logger(__name__)
        self.sharepoint_client: SharePointClient = SharePointClient(
            tenant_id=self.settings.app_tenant,
            client_id=self.settings.app_id,
            client_secret=self.settings.app_password,
        )
        self.system_logger.debug(f"Using Sharepoint Client ID: {self.sharepoint_client.client_id[:10]}")

        self.vector_store: OpenAIVectorStore = OpenAIVectorStore(vector_store_id)
        self.system_logger.debug(f"Using OpenAI Vector Store ID: {self.vector_store.get_id()} (Name: {self.vector_store.get_name()})")

        self.files_data: Dict[str, Dict[str, Any]] = {}
        self.updated_files_data: Dict[str, Dict[str, Any]] = {}
        self.running_sharepoint_file_ids: set = set()

        self._initialize_data()

    @abstractmethod
    def _initialize_data(self) -> None:
        """
        Abstract method for loading synchronization data.

        This method must be implemented by child classes to handle the specific mechanism
        for loading file metadata and synchronization state, such as from a JSON file.
        """
        pass

    def _get_sharepoint_items(
        self,
        drive_id: str,
        folder_id: str = None,
        whitelist_paths: list[str] = None,
        blacklist_paths: list[str] = None,
        keywords_to_skip: list[str] = None,
    ) -> list[dict[str, any]]:
        """
        Retrieves all relevant files from SharePoint based on the provided parameters.

        This method performs a deep search within the specified SharePoint drive and folder,
        applying optional filters to include or exclude specific file paths or types.

        Args:
            drive_id (str): The ID of the SharePoint drive.
            folder_id (str, optional): The ID of the SharePoint folder to search within. Defaults to "root".
            whitelist_paths (list[str], optional): A list of paths to include in the search. Defaults to None.
            blacklist_paths (list[str], optional): A list of paths to exclude from the search. Defaults to None.
            keywords_to_skip (list[str], optional): A list of keywords to skip when searching for files. Defaults to None.

        Returns:
            list[dict[str, any]]: A list of dictionaries representing the files found in SharePoint.
        """
        site_id : str = self.sharepoint_client.get_site_id(self.settings.site_url)
        
        self.system_logger.debug(
            f"Get all files from SharePoint Site ID: {self.settings.site_url}, Drive ID: {drive_id}."
        )

        sharepoint_files: list[dict[str, any]] = []
        try:
            sharepoint_files = retry_on_exception(max_retries=3, delay=5)(
                self.sharepoint_client.deep_search
            )(
                site_id=site_id,
                drive_id=drive_id,
                folder_id=folder_id or "root",
                whitelist_paths=whitelist_paths or [],
                blacklist_paths=blacklist_paths or [],
                keywords_to_skip=keywords_to_skip or [],
            )
            self.system_logger.debug(f"Found {len(sharepoint_files)} files/folders in SharePoint.")
        except Exception as e:
            self.system_logger.error(f"Failed to fetch SharePoint files: {e}")
            return []
        return sharepoint_files
    
    def _download_file_content(self, item: Dict[str, Any]) -> Optional[BytesIO]:
        """
        Downloads the content of a file from SharePoint into an in-memory BytesIO object.

        Args:
            item (Dict[str, Any]): A dictionary containing the file's metadata, including the download URL.

        Returns:
            Optional[BytesIO]: The file content as a BytesIO object, or None if the download fails.
        """
        try:
            file_content =  retry_on_exception(max_retries=3, delay=5)(
                self.sharepoint_client.download_file_to_memory
            )(
                download_url=item['downloadUrl']
            )
            return file_content
        except Exception as e:
            self.system_logger.error(f"Failed to download content for '{item['fullPath']}': {e}.")
            return None

    def _process_file(self, item: Dict[str, Any]) -> None:
        """
        Processes a single file from SharePoint, checking if it's new or updated.

        This method downloads a file, converts it to PDF if required (e.g., from .docx or .xlsx), and
        uploads or replaces it in the OpenAI Vector Store.

        Args:
            item (Dict[str, Any]): A dictionary containing the file's metadata from SharePoint.
        """
        if item['type'] == 'File':
            file_extension = item['extension'].lower()
            if self.settings.file_extensions and item['extension'] and file_extension not in [ext.lower() for ext in self.settings.file_extensions]:
                return

            sharepoint_file_id: str = item['id']
            self.running_sharepoint_file_ids.add(sharepoint_file_id)
            last_modified_sharepoint: datetime = datetime.fromisoformat(item['lastModified'].replace('Z', '+00:00'))

            needs_upload: bool = False
            old_openai_file_id: Optional[str] = None

            if sharepoint_file_id not in self.files_data:
                self.system_logger.debug(f"Processing new file: '{item['fullPath']}'")
                needs_upload = True
            else:
                local_file_data = self.files_data[sharepoint_file_id]
                last_modified_local: datetime = datetime.fromisoformat(local_file_data['lastModified'].replace('Z', '+00:00'))
                old_openai_file_id = local_file_data.get('fileIdOpenai')

                if last_modified_sharepoint > last_modified_local:
                    self.system_logger.debug(f"Processing updated file: '{item['fullPath']}'")
                    needs_upload = True
                else:
                    self.updated_files_data[sharepoint_file_id] = local_file_data
            
            if needs_upload:
                file_content: Optional[BytesIO] = self._download_file_content(item)
                if file_extension in ['doc', 'docx', 'xlsx']:
                    # Convert documents to PDF before uploading
                    converted_content: Optional[BytesIO] = self._convert_to_pdf(file_content, item['extension'])
                    if converted_content:
                        # item['extension'] = 'pdf'
                        # item['name'] = f"{os.path.splitext(item['name'])[0]}.pdf"
                        file_content = converted_content
                    else:
                        self.system_logger.error(f"Failed to convert '{item['fullPath']}' to PDF. Skipping upload.")
                        return

                if file_content:
                    self._upload_or_replace_file_in_openai(item, file_content, old_openai_file_id)
                else:
                    self.system_logger.error(f"No content downloaded for '{item['fullPath']}'. Cannot upload to OpenAI.")

    def _upload_or_replace_file_in_openai(self, item: Dict[str, Any], file_content: BytesIO, old_openai_file_id: Optional[str]) -> None:
        """
        Uploads a new file or replaces an existing one in the OpenAI Vector Store.

        This method handles the logic for both initial uploads and for updating existing
        documents, ensuring the correct OpenAI file ID is used for replacement.

        Args:
            item (Dict[str, Any]): A dictionary with the file's metadata from SharePoint.
            file_content (BytesIO): The content of the file to be uploaded.
            old_openai_file_id (Optional[str]): The ID of the file to be replaced in OpenAI, if it exists.
        """
        new_openai_file_id: Optional[str] = None
        try:
            if old_openai_file_id:
                self.system_logger.debug(f"Replacing file '{item['fullPath']}'.")
                new_openai_file_id = retry_on_exception(max_retries=3, delay=5)(
                    self.vector_store.replace_document_from_memory
                )(
                    old_file_id=old_openai_file_id,
                    filename=item['name'],
                    file_content=file_content
                )
            else:
                self.system_logger.debug(f"Uploading new file '{item['fullPath']}'.")
                new_openai_file_id =  retry_on_exception(max_retries=3, delay=5)(
                    self.vector_store.upload_document_from_memory
                )(
                    filename=item['name'],
                    file_content=file_content
                )
        except Exception as e:
            self.system_logger.error(f"Failed to upload/replace '{item['fullPath']}': {e}.")
            new_openai_file_id = None

        if new_openai_file_id:
            self.updated_files_data[item['id']] = {
                'fileIdSharepoint': item['id'],
                'fileIdOpenai': new_openai_file_id,
                'name': item['name'],
                'type': item['type'],
                'extension': item['extension'],
                'size': item['size'],
                'created': item['created'],
                'lastModified': item['lastModified'],
                'downloadUrl': item['downloadUrl'],
                'webUrl': item['webUrl'],
                'path': item['path'],
                'fullPath': item['fullPath'],
            }
            self.system_logger.debug(f"Successfully processed and uploaded '{item['fullPath']}'. OpenAI ID: {new_openai_file_id}")
        else:
            self.system_logger.error(f"Could not get OpenAI file ID for '{item['fullPath']}' after upload/replace attempt.")

    def _delete_stale_files_from_openai(self) -> None:
        """
        Deletes files from the OpenAI Vector Store that no longer exist in SharePoint.

        This method identifies files in the local synchronization record that were not
        found in the current SharePoint search, and then proceeds to delete them from
        the OpenAI Vector Store to maintain data consistency.
        """
        for sharepoint_file_id, local_file_data in self.files_data.items():
            if sharepoint_file_id not in self.running_sharepoint_file_ids:
                openai_file_id_to_delete = local_file_data.get("fileIdOpenai")
                if openai_file_id_to_delete:
                    self.system_logger.debug(f"File '{local_file_data['fullPath']}' (SharePoint ID: {sharepoint_file_id}) no longer exists in SharePoint. Deleting from OpenAI.")
                    try:
                        retry_on_exception(max_retries=3, delay=5)(
                        self.vector_store.delete_document
                        )(
                            file_id=openai_file_id_to_delete,
                            delete_from_storage=True
                        )
                        self.system_logger.debug(f"Successfully deleted '{openai_file_id_to_delete}' from OpenAI.")
                        if sharepoint_file_id in self.updated_files_data:
                            del self.updated_files_data[sharepoint_file_id]
                    except Exception as e:
                        self.system_logger.error(f"Failed to delete OpenAI file '{openai_file_id_to_delete}' for '{local_file_data['fullPath']}': {e}")
                else:
                    self.system_logger.warning(f"File '{local_file_data['fullPath']}' (SharePoint ID: {sharepoint_file_id}) no longer exists in SharePoint, but no OpenAI ID found to delete.")
                    if sharepoint_file_id in self.updated_files_data:
                        del self.updated_files_data[sharepoint_file_id]
    
    def _convert_to_pdf(self, file_bytes: BytesIO, file_extension: str) -> Optional[BytesIO]:
        """
        Converts the content of a file in memory to a PDF format in memory.

        This helper method uses a temporary directory to handle the conversion process
        of a file from its original format (e.g., .docx, .xlsx) to a PDF stream.

        Args:
            file_bytes (BytesIO): The content of the file as a BytesIO object.
            file_extension (str): The original extension of the file (e.g., 'docx', 'xlsx').

        Returns:
            Optional[BytesIO]: The PDF content as a BytesIO object, or None if the conversion fails.
        """
        extension: str = file_extension.lower()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_input_path = os.path.join(temp_dir, f"file.{extension}")
            temp_output_path = os.path.join(temp_dir, "file.pdf")

            with open(temp_input_path, 'wb') as temp_input_file:
                temp_input_file.write(file_bytes.getvalue())

            generated_pdf_path = convert_to_pdf(temp_input_path, temp_output_path)

            if generated_pdf_path and os.path.exists(generated_pdf_path):
                with open(generated_pdf_path, 'rb') as pdf_file:
                    pdf_bytes = BytesIO(pdf_file.read())
                    return pdf_bytes
            else:
                return None
            
    @abstractmethod
    def run_synchronization(self) -> None:
        """
        Main function to synchronize files from SharePoint to the OpenAI Vector Store.

        This abstract method orchestrates the entire synchronization process, including
        retrieving files, processing them, managing the local synchronization record,
        and handling the deletion of stale files. It must be implemented by child classes.
        """
        pass

    def purge(self, confirmation: bool = False) -> None:
        """
        Deletes all files in the OpenAI vector store and clears the local synchronization record.

        This method provides a destructive but useful function for resetting the synchronization
        state. It first attempts to delete all documents from the vector store and then
        resets the local file tracking data.

        Args:
            confirmation (bool): A flag to confirm the deletion action. The operation will only proceed if this is set to True.
        """
        all_deleted = False
        if confirmation:
            try:
                all_deleted = retry_on_exception(max_retries=3, delay=5)(
                    self.vector_store.delete_all_files
                )()
            except Exception as e:
                    self.system_logger.error(f"Failed to delete all files in vector store '{self.vector_store.get_id()}': {e}")

            if all_deleted:
                self.system_logger.info(f"All files deleted in vector store '{self.vector_store.get_id()}.")
            else:
                self.system_logger.warning(f"Some files can't be deleted in vector store '{self.vector_store.get_id()}.")

            save_json(self.settings.doc_sync_path, {})
            self._initialize_data()