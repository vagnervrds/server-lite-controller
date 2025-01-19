import json
from types import SimpleNamespace

from logger_config import setup_logger
logger = setup_logger(__name__)


def ler_settings(caminho_arquivo='settings.json'):
    """
    Lê um arquivo JSON e retorna como um objeto tipo classe.

    :param caminho_arquivo: Caminho para o arquivo JSON.
    :return: Objeto do tipo classe com os dados do JSON.
    """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            dados = json.load(
                arquivo, object_hook=lambda d: SimpleNamespace(**d))
        return dados
    except FileNotFoundError:
        logger.info(f"O arquivo {caminho_arquivo} não foi encontrado.")
        return None
    except json.JSONDecodeError:
        msg = f"Erro ao decodificar o arquivo {caminho_arquivo}"
        logger.info(msg)
        return None


def salvar_settings(objeto, caminho_arquivo='settings.json'):
    """
    Salva um objeto tipo classe em um arquivo JSON.

    :param objeto: Objeto tipo classe a ser salvo.
    :param caminho_arquivo: Caminho para salvar o arquivo JSON.
    """
    try:
        with open(caminho_arquivo, 'w', encoding='utf-8') as arquivo:
            json.dump(objeto.__dict__, arquivo, ensure_ascii=False, indent=4)
        logger.info(f"Configurações salvas com sucesso em {caminho_arquivo}.")
    except Exception as e:
        logger.info(f"Erro ao salvar o arquivo {caminho_arquivo}: {e}")
