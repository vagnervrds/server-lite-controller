from flask import Flask, render_template, request, redirect, flash, Blueprint
import secrets
from deluge_client import DelugeRPCClient
# app = Flask(__name__)
# Gerar uma chave secreta para o Flask
# app.secret_key = secrets.token_hex(16)
delugeTorrent = Blueprint('delugeTorrent', __name__)
# Configurações do Deluge
DELUGE_HOST = "localhost"  # Endereço do servidor Deluge
DELUGE_PORT = 58846        # Porta padrão do Deluge RPC
DELUGE_USERNAME = "root"   # Nome de usuário para autenticação
DELUGE_PASSWORD = "dietpi"  # Senha correspondente


def connect_deluge():
    """
    Conecta ao cliente Deluge usando as credenciais fornecidas.
    Retorna o cliente conectado ou None em caso de erro.
    """
    try:
        client = DelugeRPCClient(
            DELUGE_HOST,
            DELUGE_PORT,
            DELUGE_USERNAME,
            DELUGE_PASSWORD
        )
        client.connect()
        return client
    except Exception as e:
        print(f"Erro ao conectar ao Deluge: {e}")
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
    try:
        client = connect_deluge()
        if client:
            client.call('core.pause_torrent', [torrent_id])
            return {"message": "Download pausado com sucesso!"}, 200
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
        return {"message": f"Erro: {str(e)}"}, 500


@delugeTorrent.route('/cancel/<torrent_id>', methods=['POST'])
def cancel_torrent(torrent_id):
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
    try:
        client = connect_deluge()
        if client:
            torrents = client.call('core.get_torrents_status', {}, ['files'])
            if torrent_id.encode('utf-8') in torrents:
                files = torrents[torrent_id.encode('utf-8')][b'files']
                file_list = [{
                    "name": f[b'path'].decode('utf-8'),
                    "size": format_size(f[b'size'])  # Formata o tamanho
                } for f in files]
                return {"files": file_list}, 200
            else:
                return {"message": "Torrent não encontrado."}, 404
        else:
            return {"message": "Erro ao conectar ao Deluge."}, 500
    except Exception as e:
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


client = connect_deluge()
if client:
    print("✅ Conexão com o Deluge estabelecida com sucesso!")
else:
    print("❌ Falha ao conectar com o Deluge. Verifique as configurações.")
# if __name__ == '__main__':
#     # Testa a conexão com o Deluge ao iniciar o servidor

#     # Inicia o servidor Flask
#     app.run(host='0.0.0.0', port=5010, debug=True)
