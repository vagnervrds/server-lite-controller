import logging
import os
import glob
from datetime import datetime

_root_configured = False


class CustomRotatingFileHandler(logging.FileHandler):
    """
    Handler personalizado que rotaciona logs:
    - Limite de 1MB por arquivo
    - Máximo de 2 arquivos (atual + 1 backup)
    - Arquivos rotacionados incluem data no nome
    - O mais antigo é apagado automaticamente
    """

    def __init__(
        self, filename, max_bytes=1024 * 1024, backup_count=2, encoding="utf-8"
    ):
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.base_dir = os.path.dirname(filename)
        self.base_name = os.path.basename(filename)
        super().__init__(filename, encoding=encoding)

    def should_rollover(self):
        if self.stream is None:
            self.stream = self._open()
        self.stream.seek(0, 2)
        return self.stream.tell() >= self.max_bytes

    def do_rollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        name_without_ext, ext = os.path.splitext(self.base_name)
        backup_name = f"{name_without_ext}_{timestamp}{ext}"
        backup_path = os.path.join(self.base_dir, backup_name)

        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, backup_path)

        existing_backups = sorted(
            glob.glob(os.path.join(self.base_dir, f"{name_without_ext}_*{ext}")),
            key=os.path.getmtime,
        )

        while len(existing_backups) >= self.backup_count:
            oldest = existing_backups.pop(0)
            os.remove(oldest)

        self.stream = self._open()

    def emit(self, record):
        try:
            if self.should_rollover():
                self.do_rollover()
            logging.FileHandler.emit(self, record)
        except Exception:
            self.handleError(record)


def setup_logger(name, log_file="log.log", level=logging.INFO):
    """
    Configura o logger raiz uma única vez e retorna o logger nomeado.
    Chamadas subsequentes apenas retornam o logger do módulo correspondente.
    """
    global _root_configured

    if not _root_configured:
        log_dir = "log"
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, log_file)

        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = CustomRotatingFileHandler(
            log_path, max_bytes=1024 * 1024, backup_count=2, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        console_handler.setLevel(level)

        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(file_handler)
        root.addHandler(console_handler)

        logging.getLogger("werkzeug").setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        _root_configured = True

    return logging.getLogger(name)
