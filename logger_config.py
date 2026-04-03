import logging
import os
from logging.handlers import RotatingFileHandler

_root_configured = False


def setup_logger(name, log_file='app.log', level=logging.INFO,
                 max_bytes=5 * 1024 * 1024, backup_count=3):
    """
    Configura o logger raiz uma única vez e retorna o logger nomeado.
    Chamadas subsequentes apenas retornam o logger do módulo correspondente.
    """
    global _root_configured

    if not _root_configured:
        log_dir = 'log'
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, log_file)

        fmt = logging.Formatter(
            '%(asctime)s  %(levelname)-8s  %(name)s:%(lineno)d  %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count,
            encoding='utf-8'
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

        # Silencia bibliotecas muito verbosas
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

        _root_configured = True

    return logging.getLogger(name)
