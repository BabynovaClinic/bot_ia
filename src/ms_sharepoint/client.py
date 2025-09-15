import os
import time
import requests
from io import BytesIO
from typing_extensions import Dict, List, Optional, Any, Union

from src.log.system_logger import Logger, get_system_logger

class SharePointClient:
    """
    Represents a client for interacting with the SharePoint API.
    This class handles the authentication flow using OAuth 2.0 with Azure AD and provides
    methods to perform operations on SharePoint sites, drives, files, and folders.
    It manages the access token lifecycle to ensure all requests are authenticated.

    Features:
        - OAuth 2.0 authentication with Azure AD.
        - Access token caching and renewal.
        - SharePoint site and drive enumeration.
        - File and folder content retrieval.
        - Recursive search functionality with whitelisting and blacklisting.

    Attributes:
        system_logger (Logger): Logger for system-wide events.
        tenant_id (str): The tenant ID for the Azure AD application.
        client_id (str): The client ID of the application.
        client_secret (str): The client secret of the application.
        resource_url (str): The base URL for the Microsoft Graph API.
        base_url (str): The token endpoint URL for authentication.
        headers (Dict[str, str]): The HTTP headers for token requests.
        access_token_expiration (Optional[float]): The timestamp when the current access token expires.
        access_token (Optional[str]): The active access token for API requests.
    """
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, resource_url: str = "https://graph.microsoft.com/"):
        """
        Initializes the SharePointClient with authentication details.

        Args:
            tenant_id (str): The tenant ID for your Azure AD application.
            client_id (str): The client ID of the application.
            client_secret (str): The client secret of the application.
            resource_url (str, optional): The base URL for the Microsoft Graph API. Defaults to "https://graph.microsoft.com/".
        """
        self.system_logger: Logger = get_system_logger(__name__)
        self.tenant_id: str = tenant_id
        self.client_id: str = client_id
        self.client_secret:str = client_secret
        self.resource_url: str = resource_url
        self.base_url: str = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.headers: str = {'Content-Type': 'application/x-www-form-urlencoded'}
        self.access_token_expiration: Optional[float] = None
        self.access_token: Optional[str] = self.get_access_token()

    def get_access_token(self) -> Optional[str]:
        """
        Retrieves an access token using client credentials and stores its expiration time.

        This method performs a POST request to the Azure AD token endpoint to get an
        access token required for subsequent API calls.

        Returns:
            Optional[str]: The access token if the request is successful, otherwise None.
        """
        body: Dict[str, str]  = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': self.resource_url + '.default'
        }
        response: requests.Response = requests.post(self.base_url, headers=self.headers, data=body)
        response.raise_for_status() 
        token_data: Dict[str, Any] = response.json()
        self.access_token_expiration = time.time() + token_data.get('expires_in', 3600) - 300
        return token_data.get('access_token')
    
    def _ensure_access_token_valid(self) -> None:
        """
        Checks if the current access token is valid and refreshes it if it's expired or near expiration.

        This is a private helper method that ensures all API calls are made with a valid token,
        automatically handling token renewal to prevent authentication failures.

        Returns:
            bool: True if the token is valid, False otherwise.
        """
        if not hasattr(self, 'access_token_expiration') or time.time() >= self.access_token_expiration:
            self.system_logger.debug("Access token expired or near expiration. Renewing...")
            self.access_token = self.get_access_token()
            if not self.access_token:
                self.system_logger.error("Failed to renew access token.")
                raise Exception("Failed to renew access token.")

    def get_site_id(self, site_url: str) -> str:
        """
        Gets the SharePoint site ID from its URL.

        Args:
            site_url (str): The full URL of the SharePoint site (e.g., "contoso.sharepoint.com:/sites/marketing").

        Returns:
            str: The ID of the SharePoint site.
        """
        self._ensure_access_token_valid()
        full_url: str = f'https://graph.microsoft.com/v1.0/sites/{site_url}'
        response: requests.Response = requests.get(full_url, headers={'Authorization': f'Bearer {self.access_token}'})
        return response.json().get('id')

    def get_drives_id(self, site_id: str) -> Dict[str,str]:
        """
        Fetches all drive IDs and names within a site.

        This method retrieves a list of all document libraries and other drives associated with a
        given SharePoint site.

        Args:
            site_id (str): The ID of the SharePoint site.

        Returns:
            Dict[str, str]: A dictionary mapping drive names to their IDs.
        """
        self._ensure_access_token_valid()
        drives_url: str = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drives'
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.get(drives_url, headers=headers)
        
        if response.status_code != 200:
            self.system_logger.error(f"Error getting drives: {response.status_code} - {response.text}")
            return {}

        drives_data: List[Dict[str, Any]] = response.json().get('value', [])
    
        drives_by_name: Dict[str, str] = {drive['name']: drive['id'] for drive in drives_data}
        
        return drives_by_name
    
    def get_item_id(self, site_id: str, drive_id: str, path: str) -> Optional[str]:
        """
        Retrieves the ID of a file or folder from its path within a drive.

        This method uses a path-based approach to get the unique identifier of an item,
        which is necessary for many Graph API operations.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            path (str): The path to the item, relative to the drive's root.
                        Use forward slashes as path separators (e.g., 'FolderA/SubFolderB/document.pdf').

        Returns:
            Optional[str]: The ID of the item if found, otherwise None.
        """
        self._ensure_access_token_valid()
        
        normalized_path = os.path.normpath(path).strip('/')
        
        if not normalized_path:
            return drive_id

        # Construct the API URL using the item's path
        # The syntax ':/{path}:' is a special way to address items by path in the Graph API
        item_by_path_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{normalized_path}"
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        
        try:
            response: requests.Response = requests.get(item_by_path_url, headers=headers)
            response.raise_for_status()
            
            item_metadata: Dict[str, Any] = response.json()
            item_id: str = item_metadata.get('id')
            
            if item_id:
                return item_id
            else:
                self.system_logger.warning(f"ID not found in the response for path '{path}'.")
                return None
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.system_logger.warning(f"Item not found at path '{path}'. Status code: 404")
            else:
                self.system_logger.error(f"Error retrieving item ID for path '{path}': {e}")
                self.system_logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            self.system_logger.error(f"An unexpected error occurred: {e}")
            return None
        
    def get_lists_id(self, site_id: str) -> Dict[str, str]:
        """
        Fetches all list IDs and display names within a site.

        This method returns a mapping of all lists and document libraries by their display names
        to their unique IDs for a specified site.

        Args:
            site_id (str): The ID of the SharePoint site.

        Returns:
            Dict[str, str]: A dictionary mapping list display names to their IDs.
        """
        self._ensure_access_token_valid()
        lists_url: str = f'https://graph.microsoft.com/v1.0/sites/{site_id}/lists'
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.get(lists_url, headers=headers)
        
        if response.status_code != 200:
            self.system_logger.error(f"Error getting lists: {response.status_code} - {response.text}")
            return {}

        lists_data: List[Dict[str, Any]] = response.json().get('value', [])
    
        lists_by_name: Dict[str, str] = {lst['displayName']: lst['id'] for lst in lists_data}
        
        return lists_by_name
 
    def get_folder_content(self, site_id: str, drive_id: str, folder_id: str ="root", path: str ="") -> List[Dict[str, Any]]:
        """
        Lists only the direct files and folders inside a given folder in SharePoint (non-recursive).

        This method provides a flat view of a folder's immediate contents, including metadata like
        file type, size, and download URL. It handles pagination to retrieve all items.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            folder_id (str, optional): The ID of the folder to list contents from. Defaults to "root".
            path (str, optional): The current path for building the fullPath. Used internally.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a file or folder.
        """
        self._ensure_access_token_valid()
        folder_contents_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{folder_id}/children?$expand=listItem"
        contents_headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        
        items_list: List[Dict[str, Any]] = []

        while folder_contents_url:
            contents_response: requests.Response = requests.get(folder_contents_url, headers=contents_headers)
            if contents_response.status_code != 200:
                self.system_logger.error(f"Error fetching folder contents: {contents_response.status_code} - {contents_response.text}")
                return []

            folder_contents: Dict[str, Any] = contents_response.json()

            for item in folder_contents.get('value', []):
                item_path: str = f"{path}/{item['name']}".strip('/')
                extension: Optional[str] = None
                fields: Optional[str] = None

                if 'file' in item: 
                    extension = os.path.splitext(item['name'])[1].lstrip('.')
                    if not extension: 
                        extension = None 

                if 'listItem' in item:
                    fields = item['listItem']['fields']

                item_info: Dict[str, Any] = {
                    'id': item['id'],
                    'name': item['name'],
                    'type': 'Folder' if 'folder' in item else 'File',
                    'extension': extension,
                    'size': item.get('size', 0),
                    'created': item.get('createdDateTime', None),
                    'lastModified': item.get('lastModifiedDateTime', None),
                    'mimeType': item['file']['mimeType'] if 'file' in item else None,
                    'downloadUrl': item.get('@microsoft.graph.downloadUrl', None),
                    'webUrl': item.get('webUrl', None),
                    'path': path,
                    'fullPath': item_path,
                    'fields': fields
                }
                items_list.append(item_info)
            
            folder_contents_url = folder_contents.get('@odata.nextLink', None)

        return items_list
    
    def deep_folder_contents(self, site_id: str, drive_id: str, folder_id: str = "root", current_path: str = "", blacklist_paths: List[str] = None, keywords_to_skip: List[str] = None) -> List[Dict[str, Any]]:
        """
        Performs a deep (recursive) search, listing all files and folders
        within a given folder and its subfolders in SharePoint.

        This method traverses the folder structure, applying optional filters to
        skip certain paths or items based on keywords.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            folder_id (str, optional): The ID of the folder to start the search from.
                                        Defaults to "root" (the drive's root folder).
            current_path (str, optional): The current path for building fullPath.
                                            Used internally for recursion.
            blacklist_paths (List[str], optional): A list of full paths (case-insensitive)
                                                    to folders that should be skipped.
                                                    Defaults to None.
            keywords_to_skip (List[str], optional): A list of keywords (case-insensitive)
                                                    to skip in folder or file names.
                                                    Defaults to None.

        Returns:
            list: A list of dictionaries, where each dictionary represents a file or folder
                    with its details, including the full path.
        """
        if blacklist_paths is None:
            blacklist_paths = []
        
        if keywords_to_skip is None:
            keywords_to_skip = []
        
        norm_blacklist_paths: List[str] = [os.path.normpath(p).lower() for p in blacklist_paths]
        norm_keywords_to_skip: List[str] = [keyword.lower() for keyword in keywords_to_skip]

        all_items: List[Dict[str, Any]] = []

        norm_current_path = os.path.normpath(current_path).lower()
        if any(norm_current_path.startswith(bl_path) for bl_path in norm_blacklist_paths):
            self.system_logger.debug(f"Skipping blacklisted folder path: {current_path}")
            return []

        current_folder_items: List[Dict[str, Any]] = self.get_folder_content(site_id, drive_id, folder_id, current_path)
        
        for item in current_folder_items:
            norm_item_path: str = os.path.normpath(item['fullPath'])
            item_name_lower: str = item['name'].lower()

            if any(keyword in item_name_lower for keyword in norm_keywords_to_skip) or any(bl_path in norm_item_path.lower() for bl_path in norm_blacklist_paths):
                self.system_logger.debug(f"Skipping item/folder: {item['fullPath']}")
                continue

            all_items.append(item)

            if item['type'] == 'Folder':
                next_path: str = f"{current_path}/{item['name']}".strip('/')
                subfolder_items: List[Dict[str, Any]] = self.deep_folder_contents(
                    site_id, drive_id, item['id'], next_path, blacklist_paths, keywords_to_skip
                )
                all_items.extend(subfolder_items)

        return all_items
    
    def get_item_metadata(self, site_id: str, drive_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves metadata for a specific item (file or folder) in SharePoint,
        including custom column values.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            item_id (str): The ID of the item.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with the item's metadata if found, otherwise None.
        """
        self._ensure_access_token_valid()
        item_metadata_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{item_id}?$expand=listItem"
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.get(item_metadata_url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            self.system_logger.error(f"Error retrieving item metadata: {response.status_code} - {response.text}")
            return None
    
    def get_file_content(self, site_id: str, drive_id: str, file_id: str) -> Optional[BytesIO]:
        """
        Retrieves a file from SharePoint and loads it into memory.

        This method uses the item's ID to fetch its content, which is then stored
        in a BytesIO object, making it available for in-memory processing.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            file_id (str): The ID of the file to retrieve.

        Returns:
            Optional[BytesIO]: A BytesIO object containing the file content if successful, otherwise None.
        """
        self._ensure_access_token_valid()
        file_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{file_id}/content"
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}

        response: requests.Response = requests.get(file_url, headers=headers)
        
        if response.status_code == 200:
            return BytesIO(response.content)
        else:
            self.system_logger.error(f"Error retrieving file: {response.status_code} - {response.text}")
            return None
        
    def download_file_to_memory(self, download_url: str) -> Optional[BytesIO]:
        """
        Downloads a file from SharePoint to memory using its download URL.

        This method is useful for downloading large files directly into memory without
        the need for a temporary disk location.

        Args:
            download_url (str): The download URL for the file.

        Returns:
            Optional[BytesIO]: A BytesIO object with the file content if successful, otherwise None.
        """
        self._ensure_access_token_valid()
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.get(download_url, headers=headers)
        
        if response.status_code == 200:
            return BytesIO(response.content)
        else:
            self.system_logger.error(f"Failed to retrieve file from URL: {download_url} - {response.status_code} - {response.reason}")
            return None
        
    def download_file_to_disk(self, download_url: str, local_path: str, file_name: str) -> None:
        """
        Downloads a file from SharePoint to a local directory using its download URL.

        This method creates the necessary local directory structure and saves the file content
        to the specified path.

        Args:
            download_url (str): The download URL for the file.
            local_path (str): The local directory path where the file will be saved.
            file_name (str): The name to save the file as.
        """
        self._ensure_access_token_valid()
        headers: Dict[str, str]  = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.get(download_url, headers=headers)
        if response.status_code == 200:
            os.makedirs(local_path, exist_ok=True)
            full_path: str = os.path.join(local_path, file_name)
            full_path = os.path.normpath(full_path)
            with open(full_path, 'wb') as file:
                file.write(response.content)
            self.system_logger.debug(f"Downloaded: {full_path}")
        else:
            self.system_logger.error(f"Failed to download {file_name}: {response.status_code} - {response.reason}")

    def deep_download(self, site_id: str, drive_id: str, folder_id: str, local_base_path: str, allowed_extensions: Optional[List[str]] = None, blacklist_paths: Optional[List[str]] = None, keywords_to_skip: Optional[List[str]] = None) -> None:
        """
        Recursively downloads files from a SharePoint folder, filtering by extension
        and skipping folders based on full path or name keywords.

        This method traverses the folder hierarchy, downloading files that match the
        specified criteria and creating a mirrored folder structure on the local disk.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            folder_id (str): The ID of the folder to start downloading from.
            local_base_path (str): The base local directory to save the downloaded files.
            allowed_extensions (List[str], optional): A list of file extensions (e.g., ['pdf', 'docx'])
                                                    to download. If None or empty, all files are downloaded.
                                                    Case-insensitive.
            blacklist_paths (List[str], optional): A list of full paths (case-insensitive)
                                                    to folders that should be skipped.
                                                    Defaults to None.
            keywords_to_skip (List[str], optional): A list of keywords (case-insensitive)
                                                    to skip in folder or file names.
                                                    Defaults to None.
        """
        self.system_logger.debug(f"Starting recursive download from folder ID: {folder_id} to {local_base_path}")

        allowed_extensions_lower: Optional[List[str]] = None
        if allowed_extensions:
            allowed_extensions_lower = [ext.lower() for ext in allowed_extensions]
            self.system_logger.debug(f"Filtering by extensions: {', '.join(allowed_extensions_lower)}")
        else:
            self.system_logger.debug("No extensions specified, all files will be downloaded.")

        folder_items: List[Dict[str, Any]] = self.deep_folder_contents(site_id, drive_id, folder_id, blacklist_paths=blacklist_paths, keywords_to_skip=keywords_to_skip)

        for item in folder_items:
            full_path: str = os.path.normpath(item['fullPath'])
            local_target_dir: str = os.path.join(local_base_path, os.path.dirname(full_path))

            if item['type'] == 'Folder':
                os.makedirs(os.path.join(local_base_path, full_path), exist_ok=True)
                self.system_logger.debug(f"Created local folder: {os.path.join(local_base_path, full_path)}")
            elif item['type'] == 'File' and item.get('downloadUrl'):
                if allowed_extensions_lower:
                    if item['extension'] and item['extension'].lower() not in allowed_extensions_lower:
                        self.system_logger.debug(f"Skipping file (extension not allowed): {full_path}")
                        continue
                
                os.makedirs(local_target_dir, exist_ok=True)
                
                try:
                    self.download_file_to_disk(item['downloadUrl'], local_target_dir, item['name'])
                except requests.exceptions.RequestException as e:
                    self.system_logger.error(f"Error downloading file '{item['name']}' from '{full_path}': {e}")
                except OSError as e:
                    self.system_logger.error(f"OS error when creating directory or writing file for '{item['name']}': {e}")               
            else:
                self.system_logger.debug(f"Skipping item (not a downloadable file or folder): {full_path}")

    def upload_file(self, site_id: str, drive_id: str, folder_id: str, file_name: str, file_content: Union[bytes, BytesIO]) -> Optional[Dict[str, Any]]:
        """
        Uploads a file to a specific folder in SharePoint.

        This method handles the upload of file content, which can be provided as bytes or
        a BytesIO object, to a designated location within a SharePoint drive.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            folder_id (str): The ID of the destination folder.
            file_name (str): The name of the file to be uploaded.
            file_content (Union[bytes, BytesIO]): The content of the file.

        Returns:
            Optional[Dict[str, Any]]: The metadata of the uploaded file if successful, otherwise None.
        """
        self._ensure_access_token_valid()
        upload_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{folder_id}:/{file_name}:/content"
        headers: Dict[str, str] = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/octet-stream' # Or appropriate MIME type if known
        }
        try:
            if isinstance(file_content, BytesIO):
                file_content.seek(0) # Ensure content is read from the beginning
                data_to_upload = file_content.read()
            elif isinstance(file_content, bytes):
                data_to_upload = file_content
            else:
                self.system_logger.error("file_content must be bytes or a BytesIO object")
                raise ValueError("file_content must be bytes or a BytesIO object")

            response: requests.Response = requests.put(upload_url, headers=headers, data=data_to_upload)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            self.system_logger.debug(f"File '{file_name}' uploaded successfully.")
            return response.json()
        except requests.exceptions.HTTPError as e:
            self.system_logger.error(f"Error uploading file: {e}")
            self.system_logger.error(f"Response: {e.response.text}")
            return None
        except ValueError as e:
            self.system_logger.error(f"Invalid file_content type: {e}")
            return None
        
    def delete_file(self, site_id: str, drive_id: str, file_id: str) -> bool:
        """
        Deletes a file from SharePoint.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            file_id (str): The ID of the file to be deleted.

        Returns:
            bool: True if the deletion was successful, otherwise False.
        """
        self._ensure_access_token_valid()
        delete_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{file_id}"
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.delete(delete_url, headers=headers)
        if response.status_code == 204: # 204 No Content for successful deletion
            self.system_logger.debug(f"File with ID '{file_id}' deleted successfully.")
            return True
        else:
            self.system_logger.error(f"Error deleting file: {response.status_code} - {response.text}")
            return False
        
    def create_folder(self, site_id: str, drive_id: str, parent_folder_id: str, folder_name: str) -> Optional[Dict[str, Any]]:
        """
        Creates a new folder within a specified parent folder in SharePoint.

        This method sends a request to the Graph API to create a new folder with the
        specified name in the target parent folder.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            parent_folder_id (str): The ID of the parent folder where the new folder will be created.
            folder_name (str): The name of the new folder.

        Returns:
            Optional[Dict[str, Any]]: The metadata of the newly created folder if successful, otherwise None.
        """
        self._ensure_access_token_valid()
        create_folder_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{parent_folder_id}/children"
        headers: Dict[str, str] = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        body: Dict[str, Any] = {
            "name": folder_name,
            "folder": {}
        }
        response: requests.Response = requests.post(create_folder_url, headers=headers, json=body)
        if response.status_code == 201: # 201 Created for successful creation
            self.system_logger.debug(f"Folder '{folder_name}' created successfully.")
            return response.json()
        else:
            self.system_logger.error(f"Error creating folder: {response.status_code} - {response.text}")
            return None
        
    def search_items(self, site_id: str, drive_id: str, search_query: str) -> List[Dict[str, Any]]:
        """
        Searches for items (files/folders) within a drive by name.

        This method provides a simple, direct search capability within a SharePoint drive,
        returning a list of items that match the search query.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            search_query (str): The query string to search for.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the found items.
        """
        self._ensure_access_token_valid()
        search_url: str = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/search(q='{search_query}')"
        headers: Dict[str, str] = {'Authorization': f'Bearer {self.access_token}'}
        response: requests.Response = requests.get(search_url, headers=headers)
        if response.status_code == 200:
            return response.json().get('value', [])
        else:
            self.system_logger.error(f"Error searching items: {response.status_code} - {response.text}")
            return []

    def deep_search(self, site_id: str, drive_id: str, folder_id: str = "root", whitelist_paths: List[str] = None, blacklist_paths: List[str] = None, keywords_to_skip: List[str] = None) -> List[Dict[str, Any]]:
        """
        Performs a deep (recursive) search with whitelist and blacklist filters.

        This method allows for a comprehensive search across a drive, with the option
        to restrict the search to specific whitelisted paths or exclude certain
        blacklisted paths and keywords.

        Args:
            site_id (str): The ID of the SharePoint site.
            drive_id (str): The ID of the drive within the site.
            folder_id (str, optional): The ID of the folder to start the search from. Defaults to "root".
            whitelist_paths (List[str], optional): A list of full paths to include. Defaults to None.
            blacklist_paths (List[str], optional): A list of full paths to exclude. Defaults to None.
            keywords_to_skip (List[str], optional): A list of keywords to skip in folder or file names. Defaults to None.
            
        Returns:
            list: A list of dictionaries representing files and folders.
        """
        if keywords_to_skip is None:
            keywords_to_skip = []

        all_items = []
        if whitelist_paths:
            self.system_logger.debug(f"Using whitelist for search: {whitelist_paths}")
            for path in whitelist_paths:
                item_id = self.get_item_id(site_id, drive_id, path)
                if item_id:
                    items = self.deep_folder_contents(site_id, drive_id, item_id, path,keywords_to_skip=keywords_to_skip)
                    all_items.extend(items)

        else:
            if blacklist_paths:
                self.system_logger.debug(f"Using blacklist for search: {blacklist_paths}")
                all_items = self.deep_folder_contents(site_id, drive_id, folder_id, blacklist_paths=blacklist_paths, keywords_to_skip=keywords_to_skip)
            else:
                self.system_logger.debug("No whitelist or blacklist provided, performing a full deep search.")
                all_items = self.deep_folder_contents(site_id, drive_id, folder_id, keywords_to_skip=keywords_to_skip)            
            
        return all_items