import logging
from logging.handlers import RotatingFileHandler


def setup_logger(name, log_file='app.log', level=logging.DEBUG, max_bytes=200 * 1024, backup_count=5):
    """
    Configura um logger com rotação de arquivo e saída no terminal.

    :param name: Nome do logger (geralmente o nome do módulo).
    :param log_file: Nome do arquivo de log.
    :param level: Nível de log.
    :param max_bytes: Tamanho máximo do arquivo de log em bytes.
    :param backup_count: Número máximo de backups de log.
    :return: Instância configurada do logger.
    """
    # Configuração do handler de arquivo com rotação
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    # Configuração do handler de saída no terminal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    )

    # Configurar o logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
