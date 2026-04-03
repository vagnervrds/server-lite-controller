"""
utils.py - Funções utilitárias de configuração.
A interface pública (ler_settings, salvar_settings, salvar_settings_dict)
é mantida idêntica para não quebrar os arquivos que já a utilizam.
"""

import database as db
from logger_config import setup_logger

logger = setup_logger(__name__)


def ler_settings(_caminho_arquivo='settings.json'):
    """
    Retorna as configurações como SimpleNamespace, mantendo compatibilidade
    com o código existente que acessa settings.DOWNLOAD_DIR, settings.delug.*, etc.
    """
    try:
        return db.get_settings_namespace()
    except Exception as e:
        logger.error(f"Erro ao ler configurações do banco: {e}")
        return None


def salvar_settings(objeto, _caminho_arquivo='settings.json'):
    """Salva um objeto SimpleNamespace nas configurações."""
    try:
        data = {}
        for key, value in vars(objeto).items():
            if hasattr(value, '__dict__'):
                data[key] = vars(value)
            else:
                data[key] = value
        db.set_settings_from_dict(data)
        logger.info("Configurações salvas com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao salvar configurações: {e}")


def salvar_settings_dict(dados, _caminho_arquivo='settings.json'):
    """Salva um dicionário nas configurações. Retorna True em caso de sucesso."""
    try:
        db.set_settings_from_dict(dados)
        logger.info("Configurações salvas com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar configurações: {e}")
        return False
