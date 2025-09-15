from src.sync.services.document_synchronizer import DocumentSynchronizer
from src.sync.services.reference_synchronizer import ReferenceSynchronizer
from src.log.system_logger import Logger, get_system_logger
from src.config.settings import Settings, get_settings

class SynchronizerManager:
    """
    Manages and orchestrates the execution of multiple synchronizers.

    This class centralizes the initialization and execution logic for document
    and reference synchronizers, ensuring the synchronization process can be
    started in a unified manner. It's responsible for sequentially running
    the synchronization tasks for different types of data, such as documents
    and references, and logging the status of these operations.

    Features:
        - Initializes and holds instances of various synchronizer services.
        - Provides a single method to trigger the entire synchronization process.
        - Logs the start, completion, and any errors that occur during synchronization.

    Attributes:
        settings (Settings): The application settings.
        system_logger (Logger): A logger for recording system and synchronization events.
        document_synchronizer (DocumentSynchronizer): An instance for synchronizing documents.
        reference_synchronizer (ReferenceSynchronizer): An instance for synchronizing references.
    """

    def __init__(self):
        """
        Initializes a new instance of the SynchronizerManager.

        This constructor sets up the logger and creates instances of the
        DocumentSynchronizer and ReferenceSynchronizer, which are responsible
        for handling the specific synchronization tasks.
        """
        self.settings: Settings = get_settings()
        self.system_logger: Logger = get_system_logger(__name__)
        self.document_synchronizer: DocumentSynchronizer = DocumentSynchronizer()
        self.reference_synchronizer: ReferenceSynchronizer = ReferenceSynchronizer()

    def run_synchronization(self) -> None:
        """
        Executes the synchronization process for all managed data types.

        This method calls the `run_synchronization` method for each
        synchronizer in sequence. It logs the beginning and end of the
        master process and captures any exceptions that occur during
        the individual synchronization runs to prevent the entire process
        from failing.
        """
        self.system_logger.info("Starting master synchronization process.")

        try:
            self.document_synchronizer.run_synchronization()
        except Exception as e:
            self.system_logger.error(f"Document synchronization failed: {e}")
        
        try:
            self.reference_synchronizer.run_synchronization()
        except Exception as e:
            self.system_logger.error(f"Reference synchronization failed: {e}")

        self.system_logger.info("Master synchronization process completed.")
