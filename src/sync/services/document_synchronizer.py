import re
from typing import Dict, List, Any

from src.config.settings import Settings, get_settings
from .base_synchronizer import BaseFileSynchronizer, save_json, load_json

SETTINGS: Settings = get_settings()
FILE_PATTERN: str = r'([A-Z]{2}-[A-Z]{2}-\d{2})'

class DocumentSynchronizer(BaseFileSynchronizer):
    """
    Represents a synchronizer specifically for documents, extending the base synchronization logic.

    This class specializes in synchronizing specific document types from SharePoint to an OpenAI Vector Store. It
    implements the abstract methods of the base class to handle file data initialization and the full
    synchronization lifecycle, including fetching, processing, and cleaning up files.

    Features:
        - Specialization of `BaseFileSynchronizer` for a specific set of documents.
        - Retrieval of files based on predefined SharePoint drive and path filters.
        - Grouping of documents based on a specific file naming pattern.
        - Saving of document metadata (name, path, URLs) to a local file.
        - Orchestration of the full synchronization process, including file processing and cleanup.

    Attributes:
        files_data (Dict[str, Dict[str, Any]]): Inherited from `BaseFileSynchronizer`, stores the synchronization state.
        updated_files_data (Dict[str, Dict[str, Any]]): Inherited, tracks changes during the current run.
        running_sharepoint_file_ids (set): Inherited, tracks processed files during the current run.
    """
    def __init__(self, vector_store_id: str  = None):
        """
        Initializes the DocumentSynchronizer with a specified or default vector store ID.

        Args:
            vector_store_id (str, optional): The ID of the OpenAI Vector Store.
        """
        super().__init__(vector_store_id=vector_store_id or SETTINGS.openai_vector_store_id_sgc)

    def _initialize_data(self) -> None:
        """
        Loads the synchronization data from the local synchronization file and initializes tracking dictionaries.

        This method reads the last known state of synchronized files from a local JSON file,
        ensuring that the synchronizer starts with the correct information to detect new or updated files.
        """
        self.files_data: Dict[str, Dict[str, Any]] = load_json(self.settings.doc_sync_path)
        self.updated_files_data: Dict[str, Dict[str, Any]] = self.files_data.copy()
        self.running_sharepoint_file_ids: set = set()

    def _get_sharepoint_documents(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieves files from SharePoint, filters them, and groups them by a specific pattern.

        This method uses the base class's `_get_sharepoint_items` to fetch files from SharePoint and then
        applies additional filtering and grouping logic specific to document synchronization,
        based on file extensions and a defined filename pattern.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A dictionary where keys are file codes (extracted from filenames)
            and values are lists of file metadata dictionaries. Returns an empty dictionary if no files are found.
        """
        sharepoint_items: List[Dict[str, Any]] = self._get_sharepoint_items(
            drive_id=self.settings.drive_id_sgc,
            whitelist_paths=self.settings.whitelist_paths,
            blacklist_paths=self.settings.blacklist_paths,
            keywords_to_skip=self.settings.keywords_to_skip
        )
        if not sharepoint_items:
            self.system_logger.error("No files fetched from SharePoint.")
            return {}
        
        sharepoint_files: List[Dict[str, Any]] = [i for i in sharepoint_items if i["extension"] in self.settings.file_extensions and i["type"] == "File"]
        if not sharepoint_files:
            self.system_logger.error("No files with supported extensions found in SharePoint.")
            return {}
        
        sharepoint_documents = {}

        for i in sharepoint_files:
            filename = i['name']
            match = re.search(FILE_PATTERN, filename)
            if match:
                code = match.group(1)
                if code not in sharepoint_documents:
                    sharepoint_documents[code] = []
                sharepoint_documents[code].append(i)

        return sharepoint_documents

    def _save_sharepoint_doc_metadata(self, sharepoint_documents: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Saves relevant information about SharePoint files (name, path, URLs) to a JSON file.

        This method iterates through the grouped documents and extracts key metadata, which is then
        serialized and saved to a local file for external use or future reference.

        Args:
            sharepoint_documents (Dict[str, List[Dict[str, Any]]]): A dictionary of documents grouped by code.
        """
        document_data: Dict = {}
        for key, value in sharepoint_documents.items():
            for item in value:
                document_info: Dict = {
                    "name": item['name'],
                    "extension": item['extension'],
                    "path": item['path'],
                    "webUrl": item['webUrl'],
                    "downloadUrl": item['downloadUrl']
                }
                if key not in document_data:
                    document_data[key] = []
                document_data[key].append(document_info)
        save_json(self.settings.doc_meta_path, document_data)

    def run_synchronization(self) -> None:
        """
        Orchestrates the main synchronization process from SharePoint to the OpenAI Vector Store.

        This method first fetches and groups documents from SharePoint. It then saves the
        metadata of these documents locally. Following that, it processes each file (checking
        for updates, converting, and uploading). Finally, it cleans up any stale files
        in the vector store and updates the local synchronization record.
        """
        self.system_logger.info("Starting SharePoint Document synchronization.")
        
        sharepoint_documents: Dict[str, List[Dict]] = self._get_sharepoint_documents()

        if not sharepoint_documents:
            return

        self._save_sharepoint_doc_metadata(sharepoint_documents)

        for _, value in sharepoint_documents.items():
            for item in value:
                self._process_file(item)

        self._delete_stale_files_from_openai()

        save_json(self.settings.doc_sync_path, self.updated_files_data)
        self._initialize_data()
        self.system_logger.info("SharePoint Document synchronization completed.")