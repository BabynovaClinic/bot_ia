import os
import openai
import asyncio
import time
from typing import Dict, Optional, Union, List, Tuple
from io import BytesIO

from openai.types.vector_store import VectorStore
from openai.types.vector_stores.vector_store_file import VectorStoreFile
from openai.types.vector_stores.vector_store_file_batch import VectorStoreFileBatch
from openai.types.file_object import FileObject
from openai.types.file_deleted import FileDeleted
from src.config.settings import Settings, get_settings
from src.log.system_logger import Logger, get_system_logger

class OpenAIVectorStore:
    """
    Manages a Vector Store and its files within the OpenAI platform.

    This class provides a comprehensive interface for creating, managing, and
    deleting vector stores and their associated files. It handles both file
    uploads from local storage and in-memory content.

    Features:
        - Creation and retrieval of OpenAI Vector Stores.
        - Uploading, listing, and deleting of individual documents.
        - Efficient batch uploading of multiple files.
        - Document replacement functionality.
        - Handles pagination for listing a large number of files.

    Attributes:
        settings (Settings): Application settings.
        system_logger (Logger): Logger for system-wide events.
        api_key (str): The OpenAI API key for authentication.
        client (openai.OpenAI): The OpenAI API client.
        vector_store_id (str): The ID of the vector store in use.
        default_name (str): The default name for newly created vector stores.
        vector_store (VectorStore): The active vector store object.
    """
    def __init__(self, vector_store_id: Optional[str] = None, api_key: Optional[str] = None, default_name: Optional[str] = "Vector Store"):
        self.settings: Settings = get_settings()
        self.system_logger: Logger = get_system_logger(__name__)
        self.api_key = api_key or self.settings.openai_api_key
        if not self.api_key:
            self.system_logger.critical("The OpenAI API key was not found. Please provide it or set it as the 'OPENAI_API_KEY' environment variable.")
            raise ValueError("The OpenAI API key was not found. Please provide it or set it as the 'OPENAI_API_KEY' environment variable.")

        self.client: openai.OpenAI = openai.OpenAI(api_key=self.api_key)
        self.vector_store_id: str = vector_store_id
        self.default_name: str = default_name
        self.vector_store: VectorStore = None
        self._ensure_vector_store()
        
    def create_vector_store(self, name: str = "Vector Store", metadata: Optional[dict] = None) -> None:
        """
        Creates a new vector store with a specified name and metadata.

        Args:
            name (str): The name for the new vector store.
            metadata (Optional[dict]): Optional key-value pairs to associate with the vector store.
        """
        self.vector_store = self.client.vector_stores.create(name=name, metadata=metadata)
        self.vector_store_id = self.vector_store.id

    def _ensure_vector_store(self) -> None:
        """
        Ensures that a vector store is initialized.

        If `vector_store_id` is provided during instantiation, it attempts to retrieve the
        existing store. Otherwise, it creates a new one. This method is called internally
        by all other methods to guarantee a valid vector store is available.
        """
        if self.vector_store:
            return
        
        if self.vector_store_id:
            try:
                self.vector_store = self.client.vector_stores.retrieve(self.vector_store_id)
                self.system_logger.info(f"Using existing vector store Name: {self.vector_store.name}, ID: {self.vector_store_id}")
            except openai.NotFoundError:
                self.system_logger.warning(f"Vector store with ID '{self.vector_store_id}' not found. Creating a new one.")
                self.create_vector_store(self.default_name)
                self.system_logger.info(f"New vector store created with ID: {self.vector_store_id}")
            except Exception as e:
                self.system_logger.error(f"Error while trying to retrieve existing store vector: {e}")
                raise RuntimeError(f"Error while trying to retrieve existing store vector: {e}")
        else:
            self.system_logger.info("No vector_store_id provided. Creating a new vector store...")
            self.create_vector_store(self.default_name)
            self.system_logger.info(f"New vector store created with ID: {self.vector_store_id}")

    def get_id(self) -> Optional[str]:
        """
        Retrieves the ID of the current vector store.

        Returns:
            Optional[str]: The ID of the vector store, or None if not available.
        """
        self._ensure_vector_store()
        return self.vector_store_id
    
    def get_name(self) -> Optional[str]:
        """
        Retrieves the name of the current vector store.

        Returns:
            Optional[str]: The name of the vector store, or None if not available.
        """
        self._ensure_vector_store()
        return self.vector_store.name
    
    def upload_document_from_file(self, file_path: str) -> Optional[str]:
        """
        Uploads a document from a local file path to OpenAI and adds it to the vector store.

        Args:
            file_path (str): The path to the local file to be uploaded.

        Returns:
            Optional[str]: The ID of the uploaded file, or None if the upload fails.
        """
        self._ensure_vector_store()
        if not self.vector_store_id:
            self.system_logger.warning("There is no vector store available for uploading files.")
            return None

        try:
            self.system_logger.info(f"Uploading file '{file_path}' to OpenAI...")
            with open(file_path, "rb") as f:
                openai_file: FileObject = self.client.files.create(
                    file=f,
                    purpose='assistants'
                )
            self.system_logger.info(f"File '{file_path}' uploaded to OpenAI with ID: {openai_file.id}")

            self.system_logger.info(f"Adding file '{openai_file.id}' to vector store '{self.vector_store_id}'...")
            vector_store_file: VectorStoreFile = self.client.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=openai_file.id
            )
            self.system_logger.info(f"File '{openai_file.id}' added to vector store '{self.vector_store_id}'.")
            return openai_file.id
        except FileNotFoundError:
            self.system_logger.error(f"File not found at path: {file_path}")
            return None
        except Exception as e:
            self.system_logger.error(f"Error uploading document and adding it to the vector store: {e}")
            return None
        
    def upload_document_from_memory(self, filename: str, file_content: BytesIO) -> Optional[str]:
        """
        Uploads a document from an in-memory BytesIO object to OpenAI and adds it to the vector store.

        Args:
            filename (str): The name to give the uploaded file (e.g., "document.pdf").
            file_content (BytesIO): The binary content of the file.

        Returns:
            Optional[str]: The ID of the uploaded file, or None if the upload fails.
        """
        self._ensure_vector_store()
        if not self.vector_store_id:
            self.system_logger.warning("There is no vector store available for uploading files.")
            return None

        try:
            self.system_logger.info(f"Uploading file '{filename}' to OpenAI...")
            openai_file: FileObject = self.client.files.create(
                file=(filename, file_content),
                purpose='assistants'
            )
            self.system_logger.info(f"File '{filename}' uploaded to OpenAI with ID: {openai_file.id}")

            self.system_logger.info(f"Adding file '{openai_file.id}' to vector store '{self.vector_store_id}'...")
            vector_store_file: VectorStoreFile = self.client.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=openai_file.id
            )
            self.system_logger.info(f"File '{openai_file.id}' added to vector store '{self.vector_store_id}'.")
            return openai_file.id
        except Exception as e:
            self.system_logger.error(f"Error uploading document and adding it to the vector store: {e}")
            return None
        
    def list_files(self) -> List[dict]:
        """
        Lists all files currently associated with the vector store.

        This method handles pagination automatically to retrieve all files, regardless
        of the total count.

        Returns:
            List[dict]: A list of dictionaries, where each dictionary represents a file.
        """
        self._ensure_vector_store()
        if not self.vector_store_id:
            self.system_logger.warning("There is no vector store available for listing files.")
            return []

        all_file_details: List[dict] = []
        last_file_id: Optional[str] = None
        has_more: bool = True
        limit_per_page: int = 100

        try:
            while has_more:
                if last_file_id:
                    files_page = self.client.vector_stores.files.list(
                        vector_store_id=self.vector_store_id,
                        limit=limit_per_page,
                        after=last_file_id
                    )
                else:
                    files_page = self.client.vector_stores.files.list(
                        vector_store_id=self.vector_store_id,
                        limit=limit_per_page
                    )
                
                current_page_files: List = [file.model_dump() for file in files_page.data]
                all_file_details.extend(current_page_files)

                has_more = files_page.has_next_page
                if has_more and current_page_files:
                    last_file_id = current_page_files[-1]['id']
                elif not current_page_files:
                    has_more = False

            self.system_logger.info(f"Total files in vector store '{self.vector_store_id}': {len(all_file_details)}")
            return all_file_details
        except Exception as e:
            self.system_logger.error(f"Error listing files in vector store '{self.vector_store_id}': {e}")
            return []

    def get_file_details(self, file_id: str) -> Optional[dict]:
        """
        Retrieves the details of a specific file within the vector store.

        Args:
            file_id (str): The ID of the file to retrieve details for.

        Returns:
            Optional[dict]: A dictionary with the file's details, or None if not found or an error occurs.
        """
        self._ensure_vector_store()
        if not self.vector_store_id:
            self.system_logger.warning("There is no vector store available for uploading files.")
            return None
        try:
            file_in_vs: VectorStoreFile = self.client.vector_stores.files.retrieve(
                vector_store_id=self.vector_store_id,
                file_id=file_id
            )
            return file_in_vs.model_dump()
        except openai.NotFoundError:
            self.system_logger.error("File '{file_id}' not found in vector store '{self.vector_store_id}'.")
            return None
        except Exception as e:
            self.system_logger.error(f"Error getting details of file '{file_id}': {e}")
            return None
        
    def delete_document(self, file_id: str, delete_from_storage: bool = False) -> bool:
        """
        Deletes a document from the vector store and optionally from OpenAI's storage.

        This method first removes the file's association from the vector store. If
        `delete_from_storage` is True, it also permanently deletes the file from
        the OpenAI platform.

        Args:
            file_id (str): The ID of the file to delete.
            delete_from_storage (bool): If True, the file is also deleted from OpenAI's storage.

        Returns:
            bool: True if the deletion was successful in both requested locations, False otherwise.
        """
        self._ensure_vector_store()
        if not self.vector_store_id:
            self.system_logger.warning("There is no vector store available for uploading files.")
            return False

        success_vs: bool = False
        try:
            response_vs: FileDeleted = self.client.vector_stores.files.delete(
                vector_store_id=self.vector_store_id,
                file_id=file_id
            )
            if response_vs.deleted:
                self.system_logger.info(f"File '{file_id}' deleted from vector store '{self.vector_store_id}'.")
                success_vs = True
            else:
                self.system_logger.warning(f"Could not delete file '{file_id}' from the vector store.")
        except Exception as e:
            self.system_logger.error(f"Error deleting file '{file_id}' from vector store: {e}")

        success_openai_storage: bool = True

        if delete_from_storage:
            try:
                response_storage: FileDeleted = self.client.files.delete(file_id)
                if response_storage.deleted:
                    self.system_logger.info(f"File '{file_id}' permanently deleted from OpenAI storage.")
                    success_openai_storage = True
                else:
                    self.system_logger.warning(f"Could not delete file '{file_id}' from OpenAI storage.")
                    success_openai_storage = False
            except Exception as e:
                self.system_logger.error(f"Error deleting file '{file_id}' from OpenAI storage: {e}")
                success_openai_storage = False
        
        return success_vs and success_openai_storage
    
    def replace_document_from_file(self, old_file_id: str, new_file_path: str) -> Optional[str]:
        """
        Replaces an existing document in the vector store with a new one from a local file.

        The old file is deleted from both the vector store and OpenAI storage before
        the new file is uploaded and added.

        Args:
            old_file_id (str): The ID of the document to be replaced.
            new_file_path (str): The path to the new document file.

        Returns:
            Optional[str]: The ID of the newly uploaded file, or None if the operation fails.
        """
        self.system_logger.info(f"Trying to replace file '{old_file_id}' with '{new_file_path}'...")
        delete_success: bool = self.delete_document(old_file_id, delete_from_storage=True)
        if not delete_success:
            self.system_logger.info(f"Could not delete old file '{old_file_id}'. Aborting replacement.")
            return None
        
        new_file_id: Optional[str]  = self.upload_document_from_file(new_file_path)
        if new_file_id:
            self.system_logger.info(f"File '{old_file_id}' successfully replaced by '{new_file_id}'.")
        else:
            self.system_logger.warning(f"The old file '{old_file_id}' was deleted, but the new file '{new_file_path}' could not be uploaded.")
            return None
        
        return new_file_id
    
    def replace_document_from_memory(self, old_file_id: str, filename: str, file_content: BytesIO) -> Optional[str]:
        """
        Replaces an existing document with new content provided from memory.

        The old file is deleted from the vector store and OpenAI storage before the
        new in-memory content is uploaded and added.

        Args:
            old_file_id (str): The ID of the document to be replaced.
            filename (str): The name for the new file.
            file_content (BytesIO): The content of the new file.

        Returns:
            Optional[str]: The ID of the newly uploaded file, or None if the operation fails.
        """
        self.system_logger.info(f"Trying to replace file '{old_file_id}' with '{filename}'...")
        delete_success: bool = self.delete_document(old_file_id, delete_from_storage=True)
        if not delete_success:
            self.system_logger.info(f"Could not delete old file '{old_file_id}'. Aborting replacement.")
            return None
        
        new_file_id: Optional[str] = self.upload_document_from_memory(filename, file_content)
        if new_file_id:
            self.system_logger.info(f"File '{old_file_id}' successfully replaced by '{new_file_id}'.")
        else:
            self.system_logger.warning(f"The old file '{old_file_id}' was deleted, but the new file '{filename}' could not be uploaded.")
            return None
        
        return new_file_id
    
    def upload_documents_batch_from_file(self, file_paths: List[str]) -> Tuple[Optional[str], int, int]:
        """
        Uploads multiple documents from local file paths to the vector store in a single batch.

        This method first uploads each file individually and then adds them to the vector
        store in a batch, which is more efficient for multiple files.

        Args:
            file_paths (List[str]): A list of paths to the files to be uploaded.

        Returns:
            Tuple[Optional[str], int, int]: A tuple containing the batch ID, the number of
                                            successfully completed files, and the number of
                                            failed files.
        """
        uploaded_files: dict = {}
        for file_path in file_paths:
            file_id: str = self.upload_document_from_file(file_path)
            uploaded_files[file_path] = file_id

        uploaded_file_ids: List[str] = [i for i in uploaded_files.values() if i is not None]

        try:
            self.system_logger.info(f"Adding {len(uploaded_file_ids)} files to the vector store '{self.vector_store_id}' in batch...")
            batch_add: VectorStoreFileBatch = self.client.vector_stores.file_batches.create(
                vector_store_id=self.vector_store_id,
                file_ids=uploaded_file_ids
            )
            self.system_logger.info(f"Batch of files sent. Batch ID: {batch_add.id}. Status: {batch_add.status}")

            while batch_add.status in ["in_progress", "queued", "cancelling"]:
                time.sleep(1)
                batch_add = self.client.vector_stores.file_batches.retrieve(
                    vector_store_id=self.vector_store_id,
                    batch_id=batch_add.id
                )
                self.system_logger.info(f"Batch status: {batch_add.status} (processed: {batch_add.file_counts.completed}, failed: {batch_add.file_counts.failed})")

            return batch_add.id, batch_add.file_counts.completed, batch_add.file_counts.failed
        
        except Exception as e:
            self.system_logger.error(f"Error processing file batch: {e}")
            return None, 0, 0

    def upload_documents_batch_from_memory(self, files: List[Tuple[str, BytesIO]]) -> Tuple[Optional[str], int, int]:
        """
        Uploads multiple documents from in-memory objects to the vector store in a batch.

        This method first uploads each file individually and then adds them to the vector
        store in a batch, which is more efficient for multiple files.

        Args:
            files (List[Tuple[str, BytesIO]]): A list of tuples, each containing a filename
                                            and its corresponding BytesIO content.

        Returns:
            Tuple[Optional[str], int, int]: A tuple containing the batch ID, the number of
                                            successfully completed files, and the number of
                                            failed files.
        """
        uploaded_file_ids: List[str] = []
        for filename, file_content in files:
            file_id =self.upload_document_from_memory(filename, file_content)
            uploaded_file_ids.append(file_id)

        uploaded_file_ids = [i for i in uploaded_file_ids if i is not None]

        try:
            self.system_logger.info(f"Adding {len(uploaded_file_ids)} files to the vector store '{self.vector_store_id}' in batch...")
            batch_add: VectorStoreFileBatch = self.client.vector_stores.file_batches.create(
                vector_store_id=self.vector_store_id,
                file_ids=uploaded_file_ids
            )
            self.system_logger.info(f"Batch of files sent. Batch ID: {batch_add.id}. Status: {batch_add.status}")

            while batch_add.status in ["in_progress", "queued", "cancelling"]:
                time.sleep(1)
                batch_add = self.client.vector_stores.file_batches.retrieve(
                    vector_store_id=self.vector_store_id,
                    batch_id=batch_add.id
                )
                self.system_logger.info(f"Batch status: {batch_add.status} (processed: {batch_add.file_counts.completed}, failed: {batch_add.file_counts.failed})")

            return batch_add.id, batch_add.file_counts.completed, batch_add.file_counts.failed
        
        except Exception as e:
            self.system_logger.error(f"Error processing file batch: {e}")
            return None, 0, 0
        
    def delete_all_files(self) -> bool:
        """
        Deletes all files from the associated vector store.

        This operation iterates through all files in the store and attempts to delete
        each one individually from both the vector store and OpenAI's permanent storage.

        Returns:
            bool: True if all files were deleted successfully, False otherwise.
        """
        self._ensure_vector_store()
        if not self.vector_store_id:
            self.system_logger.warning("No vector store ID found. Cannot delete files.")
            return False

        try:
            files_to_delete = self.list_files()
            if not files_to_delete:
                self.system_logger.info(f"No files found in vector store '{self.vector_store_id}' to delete.")
                return True

            all_deleted_successfully = True
            for file_detail in files_to_delete:
                file_id = file_detail.get('id')
                if file_id:
                    self.system_logger.info(f"Deleting file '{file_id}' from vector store '{self.vector_store_id}'...")
                    if not self.delete_document(file_id, delete_from_storage=True):
                        self.system_logger.error(f"Failed to delete file '{file_id}'.")
                        all_deleted_successfully = False
                else:
                    self.system_logger.warning("Found a file entry without an ID. Skipping.")
                    all_deleted_successfully = False

            if all_deleted_successfully:
                self.system_logger.info(f"All files successfully deleted from vector store '{self.vector_store_id}'.")
            else:
                self.system_logger.warning(f"Some files could not be deleted from vector store '{self.vector_store_id}'.")
            return all_deleted_successfully

        except Exception as e:
            self.system_logger.error(f"An error occurred while trying to delete all files from vector store '{self.vector_store_id}': {e}")
            return False