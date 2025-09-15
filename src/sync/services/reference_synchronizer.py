import os
from typing import Dict, List, Any

from src.config.settings import Settings, get_settings
from .base_synchronizer import BaseFileSynchronizer, save_json, load_json

SETTINGS: Settings = get_settings()

class ReferenceSynchronizer(BaseFileSynchronizer):
    """
    Represents a synchronizer for medical reference documents, extending the base synchronization logic.

    This class specializes in synchronizing medical reference files from a specific SharePoint drive to an
    OpenAI Vector Store. It implements the necessary methods from the base class to handle
    the full synchronization lifecycle, including fetching files, extracting specific metadata fields,
    and managing the local and vector store records.

    Features:
        - Specialization of `BaseFileSynchronizer` for a specific set of medical reference documents.
        - Retrieval of files from a predefined SharePoint drive.
        - Grouping of documents based on their filename.
        - Extraction and saving of specific metadata fields (e.g., authors, title, year) to a local file.
        - Orchestration of the full synchronization process, including file processing and cleanup.

    Attributes:
        files_data (Dict[str, Dict[str, Any]]): Inherited from `BaseFileSynchronizer`, stores the synchronization state.
        updated_files_data (Dict[str, Dict[str, Any]]): Inherited, tracks changes during the current run.
        running_sharepoint_file_ids (set): Inherited, tracks processed files during the current run.
    """
    def __init__(self, vector_store_id: str = None):
        """
        Initializes the ReferenceSynchronizer with a specified or default vector store ID.

        Args:
            vector_store_id (str, optional): The ID of the OpenAI Vector Store. Defaults to the value from settings.
        """
        super().__init__(vector_store_id=vector_store_id or SETTINGS.openai_vector_store_id_ref)

    def _initialize_data(self) -> None:
        """
        Loads the synchronization data from the local synchronization file and initializes tracking dictionaries.

        This method reads the last known state of synchronized files from a local JSON file,
        ensuring that the synchronizer starts with the correct information to detect new or updated files.
        """
        self.files_data: Dict[str, Dict[str, Any]] = load_json(self.settings.ref_sync_path)
        self.updated_files_data: Dict[str, Dict[str, Any]] = self.files_data.copy()
        self.running_sharepoint_file_ids: set = set()

    def _get_sharepoint_references(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieves files from a specific SharePoint drive and groups them by filename.

        This method uses the base class's `_get_sharepoint_items` to fetch all items from the designated
        SharePoint drive and then groups them into a dictionary where the key is the filename (without extension)
        and the value is a list of file metadata.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A dictionary where keys are filenames and values are lists of file metadata.
            Returns an empty dictionary if no files are fetched.
        """
        sharepoint_items: List[Dict[str, Any]] = self._get_sharepoint_items(
            drive_id=self.settings.drive_id_ref,
        )
        if not sharepoint_items:
            self.system_logger.error("No files fetched from SharePoint.")
            return {}
        
        sharepoint_references: Dict = {}

        for i in sharepoint_items:
            filename = os.path.splitext(i["name"])[0]
            if filename not in sharepoint_references:
                sharepoint_references[filename] = []
            sharepoint_references[filename].append(i)

        return sharepoint_references

    def _save_sharepoint_ref_metadata(self, sharepoint_references: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Saves relevant metadata about SharePoint medical references to a local JSON file.

        This method iterates through the fetched and grouped references, extracting specific SharePoint
        list fields such as `Reference_x0020_Type`, `Main_x0020_Authors`, and `Reference_x0020_Title`.
        It also includes optional fields and general file information, then serializes this data to a JSON file.

        Args:
            sharepoint_references (Dict[str, List[Dict[str, Any]]]): A dictionary of references grouped by name.
        """
        reference_data: Dict = {}
        for key, value in sharepoint_references.items():
            for item in value:
                reference_info: Dict = {
                    "name": os.path.splitext(item['name'])[0],
                    "refType": item['fields'].get('Reference_x0020_Type'),
                    "mainAuthors": item['fields'].get('Main_x0020_Authors'),
                    "title": item['fields'].get('Reference_x0020_Title'),
                    "year": item['fields'].get('Publication_x0020_Year'),
                }

                optional_fields: Dict = {
                    'Container_x0020_Title': "container",
                    'Publisher_x0020_Info': "publisher",
                    'Edition_x0020_Info': "edition",
                    'Pages_x0020_Info': "pages",
                    'URL_x0020_Link': "url",
                    'DOI': "doi"
                }

                for field in optional_fields.keys():
                    if field in item['fields']:
                        reference_info[optional_fields[field]] = item['fields'][field]

                reference_info["extension"] = item.get('extension')
                reference_info["webUrl"] = item.get('webUrl')
                reference_info["downloadUrl"] = item.get('downloadUrl')

                if key not in reference_data:
                    reference_data[key] = []
                reference_data[key].append(reference_info)
        
        save_json(self.settings.ref_meta_path, reference_data)

    def run_synchronization(self) -> None:
        """
        Orchestrates the main synchronization process for reference files from SharePoint to the OpenAI Vector Store.

        This method first fetches and groups documents from SharePoint. It then saves the
        metadata of these documents locally. Following that, it processes each file (checking
        for updates, converting, and uploading). Finally, it cleans up any stale files
        in the vector store and updates the local synchronization record.
        """
        self.system_logger.info("Starting SharePoint Reference synchronization.")

        sharepoint_references: Dict[str, List[Dict]] = self._get_sharepoint_references()

        if not sharepoint_references:
            return
        
        self._save_sharepoint_ref_metadata(sharepoint_references)

        for _, value in sharepoint_references.items():
            for item in value:
                self._process_file(item)

        self._delete_stale_files_from_openai()

        save_json(self.settings.ref_sync_path, self.updated_files_data)
        self._initialize_data()
        self.system_logger.info("SharePoint Reference synchronization completed.")