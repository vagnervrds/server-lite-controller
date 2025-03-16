import os
from flask import Flask, render_template, request, redirect, flash, Blueprint, jsonify
import secrets
from deluge_client import DelugeRPCClient
from logger_config import setup_logger
from utils import ler_settings

# Configurar o logger
logger = setup_logger(__name__)
settings = ler_settings()
d = settings.delug

delugeTorrent = Blueprint('delugeTorrent', __name__)


def connect_deluge():
    """
    Conecta ao cliente Deluge usando as credenciais fornecidas.
    Retorna o cliente conectado ou None em caso de erro.
    """
    try:
        client = DelugeRPCClient(
            d.DELUGE_HOST,
            d.DELUGE_PORT,
            d.DELUGE_USERNAME,
            d.DELUGE_PASSWORD
        )
        client.connect()
        return client
    except Exception as e:
        logger.info(f"Erro ao conectar ao Deluge: {e}")
        return None


@delugeTorrent.route('/', methods=['GET', 'POST'])
def index():
    """
    Rota principal que exibe a lista de downloads ativos e processa
    a adição de novos downloads via magnet link.
    """
    if request.method == 'POST':
        # Obtém o magnet link enviado pelo formulário
        magnet_link = request.form.get('magnet_link')
        if magnet_link:
            try:
                client = connect_deluge()
                if client:
                    # Adiciona o magnet link ao Deluge
                    client.call('core.add_torrent_magnet', magnet_link, {})
                    flash('Download adicionado com sucesso!', 'success')
                else:
                    flash('Erro ao conectar ao Deluge.', 'error')
            except Exception as e:
                flash(f'Erro ao adicionar download: {str(e)}', 'error')
        else:
            flash('Por favor, insira um magnet link válido.', 'error')
        return redirect('/')

    # Exibe os downloads ativos
    downloads = []
    try:
        client = connect_deluge()
        if client:
            torrents = client.call('core.get_torrents_status', {}, [
                                   'name', 'progress', 'state'])
            for torrent_id, data in torrents.items():
                downloads.append({
                    'name': data[b'name'].decode('utf-8'),
                    'progress': round(data[b'progress'], 2),
                    'state': data[b'state'].decode('utf-8')
                })
    except Exception as e:
        flash(f'Erro ao listar downloads: {str(e)}', 'error')

    return render_template('Torrent.html', downloads=downloads)


@delugeTorrent.route('/stop/<torrent_id>', methods=['POST'])
def stop_torrent(torrent_id):
    """
    Pausa um torrent específico.
    """
    try:
        client = connect_deluge()
        if client:
            client.call('core.pause_torrent', [torrent_id])
            return {"message": "Download pausado com sucesso!"}, 200
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
        return {"message": f"Erro: {str(e)}"}, 500


@delugeTorrent.route('/resume/<torrent_id>', methods=['POST'])
def resume_torrent(torrent_id):
    """
    Retoma um torrent pausado.
    """
    try:
        client = connect_deluge()
        if client:
            client.call('core.resume_torrent', [torrent_id])
            return {"message": "Download retomado com sucesso!"}, 200
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
        return {"message": f"Erro: {str(e)}"}, 500


@delugeTorrent.route('/cancel/<torrent_id>', methods=['POST'])
def cancel_torrent(torrent_id):
    """
    Cancela um torrent sem apagar os arquivos.
    """
    try:
        client = connect_deluge()
        if client:
            client.call('core.remove_torrent', torrent_id, False)
            return {"message": "Download cancelado com sucesso!"}, 200
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
        return {"message": f"Erro: {str(e)}"}, 500


@delugeTorrent.route('/delete/<torrent_id>', methods=['POST'])
def delete_torrent(torrent_id):
    """
    Remove um torrent e apaga os arquivos.
    """
    try:
        client = connect_deluge()
        if client:
            client.call('core.remove_torrent', torrent_id, True)
            return {"message": "Download e arquivos apagados com sucesso!"}, 200
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
        return {"message": f"Erro: {str(e)}"}, 500


def format_size(size_in_bytes):
    """
    Formata o tamanho do arquivo para um formato legível.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024


@delugeTorrent.route('/list-files/<torrent_id>', methods=['GET'])
def list_files(torrent_id):
    """
    Lista os arquivos de um torrent específico.
    """
    try:
        client = connect_deluge()
        if client:
            torrents = client.call('core.get_torrents_status', {}, [
                                   'files', 'file_priorities'])
            if torrent_id.encode('utf-8') in torrents:
                files = torrents[torrent_id.encode('utf-8')][b'files']
                priorities = torrents[torrent_id.encode(
                    'utf-8')].get(b'file_priorities', [])

                file_list = []
                for i, f in enumerate(files):
                    priority = priorities[i] if i < len(priorities) else 1
                    file_list.append({
                        "name": f[b'path'].decode('utf-8'),
                        "size": format_size(f[b'size']),
                        "priority": priority
                    })

                return {"files": file_list}, 200
            else:
                return {"message": "Torrent não encontrado."}, 404
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {e}")
        return {"message": f"Erro: {str(e)}"}, 500


@delugeTorrent.route('/downloads', methods=['GET'])
def get_downloads():
    """
    Endpoint que retorna a lista de downloads ativos em JSON.
    """
    downloads = []
    try:
        client = connect_deluge()
        if client:
            torrents = client.call('core.get_torrents_status', {}, [
                                   'name', 'progress', 'state'])
            for torrent_id, data in torrents.items():
                downloads.append({
                    'id': torrent_id.decode('utf-8'),
                    'name': data[b'name'].decode('utf-8'),
                    'progress': round(data[b'progress'], 2),
                    'state': data[b'state'].decode('utf-8')
                })
        return {"downloads": downloads}, 200
    except Exception as e:
        return {"error": f"Erro: {str(e)}"}, 500


@delugeTorrent.route('/cancel-files/<torrent_id>', methods=['POST'])
def cancel_files(torrent_id):
    """
    Endpoint para atualizar prioridades de arquivos em um torrent.
    Arquivos com prioridade 0 não serão baixados.
    """
    try:
        client = connect_deluge()
        if not client:
            return {"message": "Erro ao conectar ao Deluge."}, 500

        # Obtém os dados do request
        data = request.get_json()
        if not data or "file_selections" not in data:
            return {"message": "Nenhum dado enviado."}, 400

        # Ex: {"file_name_1": true, "file_name_2": false}
        file_selections = data["file_selections"]

        # Converte torrent_id para bytes se necessário
        if isinstance(torrent_id, str):
            torrent_id_bytes = torrent_id.encode('utf-8')
        else:
            torrent_id_bytes = torrent_id

        # Verifica se o torrent existe
        torrents = client.call('core.get_torrents_status', {}, ['files'])
        if torrent_id_bytes not in torrents:
            return {"message": "Torrent não encontrado."}, 404

        # Obtém a lista de arquivos do torrent
        files = torrents[torrent_id_bytes][b'files']

        # Prepara a lista de prioridades (0=não baixar, 1=normal)
        file_priorities = []
        for file in files:
            file_name = file[b'path'].decode('utf-8')
            # Se o arquivo estiver marcado como false, define prioridade 0
            # Caso contrário, define prioridade 1 (normal)
            priority = 0 if not file_selections.get(file_name, True) else 1
            file_priorities.append(priority)

        # Atualiza as prioridades dos arquivos no Deluge
        client.call('core.set_torrent_file_priorities',
                    torrent_id_bytes, file_priorities)

        return {"message": "Prioridades de arquivos atualizadas com sucesso."}, 200

    except Exception as e:
        logger.error(f"Erro ao atualizar prioridades: {e}")
        return {"message": f"Erro: {str(e)}"}, 500


# Testa a conexão com o Deluge ao iniciar o servidor
client = connect_deluge()
if client:
    logger.info("✅ Conexão com o Deluge estabelecida com sucesso!")
else:
    logger.info("❌ Falha ao conectar com o Deluge. Verifique as configurações.")
