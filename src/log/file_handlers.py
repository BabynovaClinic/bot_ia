
import os
import time
import shutil
import logging
import logging.handlers

from typing import Optional
from logging import handlers

class SafeTimedRotatingFileHandler(handlers.TimedRotatingFileHandler):
    """
    Variación de TimedRotatingFileHandler que intenta:
      - cerrar el stream antes de renombrar,
      - usar os.replace para ser más robusto,
      - reintentar varias veces si ocurre PermissionError (común en Windows).
    En fallo persistente hace un fallback copiando el archivo a un nombre con timestamp.
    """
    def __init__(self, filename: str, when: str = 'midnight', interval: int = 1,
                 backupCount: int = 7, encoding: Optional[str] = 'utf-8',
                 delay: bool = False, utc: bool = False,
                 retries: int = 5, retry_delay: float = 0.25):
        super().__init__(filename=filename, when=when, interval=interval,
                         backupCount=backupCount, encoding=encoding, delay=delay, utc=utc)
        self.retries = retries
        self.retry_delay = retry_delay

    def doRollover(self):
        """
        Copia/adapta la lógica original de TimedRotatingFileHandler.doRollover()
        pero con cierres explícitos y reintentos en os.replace/os.rename.
        """
        # Si no se abrió aún (delay=True), nada que rotar
        if self.stream:
            try:
                self.stream.flush()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        currentTime = int(time.time())
        # timestamp usado en el nombre del archivo rotado
        # suffix por defecto en TimedRotatingFileHandler es "%Y-%m-%d"
        dfn = self.rotation_filename(self.baseFilename + "." +
                                     time.strftime(self.suffix, time.localtime(self.rolloverAt - self.interval)))
        # Si ya existe el destino, tratar de eliminarlo (seguir la semántica original)
        if os.path.exists(dfn):
            try:
                os.remove(dfn)
            except Exception:
                # Si no se puede eliminar, no abortamos; intentaremos renombrar de todas formas
                pass

        renamed = False
        last_exc = None
        for attempt in range(self.retries):
            try:
                # usar replace es más robusto en algunos sistemas (sobrescribe si existe)
                os.replace(self.baseFilename, dfn)
                renamed = True
                break
            except PermissionError as e:
                last_exc = e
                time.sleep(self.retry_delay)
            except Exception as e:
                # Otros errores (ej: archivos en red), capturamos y salimos del loop de reintentos
                last_exc = e
                break

        if not renamed:
            # Fallback: intentar copiar el contenido y truncar el original para no perder logs
            try:
                if os.path.exists(self.baseFilename):
                    shutil.copy2(self.baseFilename, dfn)
                    # truncar el archivo original (abrir en modo 'w' para limpiar)
                    with open(self.baseFilename, 'w', encoding=self.encoding or 'utf-8'):
                        pass
                    renamed = True
            except Exception:
                renamed = False

        # Manejo de archivos antiguos según backupCount (sigue comportamiento original)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                try:
                    os.remove(s)
                except Exception:
                    pass

        # Reabrir el stream si no estamos en delay
        if not self.delay:
            try:
                self.stream = self._open()
            except Exception:
                # Si no se puede reabrir, dejamos stream en None; futuros logs podrían fallar,
                # pero preferimos no lanzar excepción que rompa toda la aplicación.
                self.stream = None

        # calcular el próximo rolloverAt
        newRolloverAt = self.computeRollover(currentTime)
        self.rolloverAt = newRolloverAt

    # Utilidad para calcular el próximo rollover (se respeta la lógica interna)
    def computeRollover(self, currentTime):
        return logging.handlers.TimedRotatingFileHandler.computeRollover(self, currentTime)
