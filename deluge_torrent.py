import os
import shutil
import platform
from flask import Flask, render_template, request, redirect, flash, Blueprint, jsonify
import secrets
import re
from deluge_client import DelugeRPCClient
from logger_config import setup_logger
from utils import ler_settings

# Configurar o logger
logger = setup_logger(__name__)


def _get_deluge_config():
    """Carrega as credenciais do Deluge sob demanda para evitar falhas na importação."""
    settings = ler_settings()
    if settings is None or not hasattr(settings, 'delug'):
        logger.error("Configurações do Deluge não encontradas no banco de dados.")
        return None
    return settings.delug

delugeTorrent = Blueprint('delugeTorrent', __name__,
                          template_folder='templates',
                          static_folder='static',)


def extrair_hash_magnet(magnet_link):
    """
    Extrai o hash (info_hash) de um magnet link.
    Suporta SHA-1 em hexadecimal (40 chars) ou Base32 (32 chars A-Z2-7).
    """
    # Hex (40 caracteres)
    match = re.search(r'btih:([a-f0-9]{40})', magnet_link, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    # Base32 (32 caracteres)
    match = re.search(r'btih:([A-Z2-7]{32})', magnet_link, re.IGNORECASE)
    if match:
        import base64
        try:
            decoded = base64.b32decode(match.group(1).upper())
            return decoded.hex()
        except Exception:
            return match.group(1).lower()
    return None


def torrent_ja_existe(client, info_hash):
    """
    Verifica se um torrent já existe na sessão do Deluge.
    Retorna (existe, torrent_id, nome) ou (False, None, None)
    """
    try:
        torrents = client.call('core.get_torrents_status', {}, ['name'])
        for torrent_id, data in torrents.items():
            torrent_id_str = torrent_id.decode(
                'utf-8') if isinstance(torrent_id, bytes) else torrent_id
            # Comparar o hash
            if torrent_id_str.lower() == info_hash.lower():
                nome = data[b'name'].decode(
                    'utf-8') if isinstance(data[b'name'], bytes) else data[b'name']
                return True, torrent_id_str, nome
        return False, None, None
    except Exception as e:
        logger.error(f"Erro ao verificar torrent existente: {e}")
        return False, None, None


def get_disk_usage():
    """
    Obtém informações sobre o uso do disco onde os downloads são salvos.
    Retorna um dicionário com total, usado, livre e porcentagem.
    """
    try:
        # Detectar o sistema operacional e definir o caminho correto
        settings = ler_settings()
        download_path = settings.DOWNLOAD_DIR if settings else "/mnt/dietpi_userdata/downloads"

        # Obter estatísticas do disco
        disk_stats = shutil.disk_usage(download_path)

        # Converter bytes para GB
        total_gb = disk_stats.total / (1024 ** 3)
        used_gb = disk_stats.used / (1024 ** 3)
        free_gb = disk_stats.free / (1024 ** 3)
        percent = (disk_stats.used / disk_stats.total) * 100

        return {
            "total": round(total_gb, 2),
            "used": round(used_gb, 2),
            "free": round(free_gb, 2),
            "percent": round(percent, 2),
            "path": download_path
        }
    except Exception as e:
        logger.error(f"Erro ao obter uso do disco: {e}")
        return {
            "total": 0,
            "used": 0,
            "free": 0,
            "percent": 0,
            "path": "N/A",
            "error": str(e)
        }


def _find_deluge_localclient_password():
    """
    Tenta localizar o arquivo auth do Deluge e extrair a senha do localclient.
    Retorna a senha se encontrada, ou None.
    """
    import glob

    # 1. Caminhos fixos conhecidos
    static_candidates = [
        '/mnt/dietpi_userdata/deluge/auth',
        os.path.expanduser('~/.config/deluge/auth'),
        '/var/lib/deluged/.config/deluge/auth',
        '/home/deluge/.config/deluge/auth',
        '/root/.config/deluge/auth',
        os.path.join(os.environ.get('APPDATA', ''), 'deluge', 'auth'),
    ]

    # 2. Glob: qualquer usuário em /home ou /var
    static_candidates += glob.glob('/home/*/.config/deluge/auth')
    static_candidates += glob.glob('/var/lib/*/.config/deluge/auth')
    static_candidates += glob.glob('/var/lib/*/deluge/auth')

    # 3. Tenta ler o config dir do serviço systemd do Deluge
    for service_file in glob.glob('/etc/systemd/system/deluge*.service') + \
                        glob.glob('/lib/systemd/system/deluge*.service'):
        try:
            with open(service_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if 'DELUGED_CONF' in line or '--config' in line:
                        # Extrai o caminho do config
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            conf_dir = parts[1].strip().strip('"').strip("'")
                            static_candidates.append(os.path.join(conf_dir, 'auth'))
        except Exception:
            pass

    logger.info(f"Procurando auth do Deluge em {len(static_candidates)} caminhos...")

    for path in static_candidates:
        exists = os.path.exists(path)
        logger.info(f"  {'[OK]' if exists else '[--]'} {path}")
        if exists:
            result = _read_localclient_from_auth(path)
            if result is not None:
                logger.info(f"Senha do localclient obtida de: {path}")
                return result

    logger.warning("Arquivo auth do Deluge não encontrado em nenhum caminho. Usando senha fallback 'deluge'.")
    return None


def _read_localclient_from_auth(path):
    """Lê o arquivo auth e retorna a senha do localclient, ou None se não encontrar."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('localclient:'):
                    parts = line.split(':')
                    if len(parts) >= 2 and parts[1]:
                        return parts[1]
    except Exception as e:
        logger.warning(f"Não foi possível ler {path}: {e}")
    return None


def connect_deluge():
    """
    Conecta ao cliente Deluge.
    Tenta usar credenciais do usuário 'localclient' lendo do arquivo auth local,
    o que corresponde à conexão padrão local. Caso falhe a leitura, tenta a senha 'deluge'.
    """
    try:
        d = _get_deluge_config()
        if d is None:
            logger.error("Não foi possível obter configurações do Deluge. Conexão abortada.")
            return None

        host = d.DELUGE_HOST
        if host.startswith('http://'):
            host = host.replace('http://', '')
        if host.startswith('https://'):
            host = host.replace('https://', '')

        # Tenta pegar credenciais do banco
        username = getattr(d, 'DELUGE_USERNAME', None)
        password = getattr(d, 'DELUGE_PASSWORD', None)

        if not username or not password:
            username = 'localclient'
            password = 'deluge'  # último fallback

            found_password = _find_deluge_localclient_password()
            if found_password:
                password = found_password
                # Persiste no banco para próximas conexões
                import database as _db
                _db.set_setting('delug.DELUGE_USERNAME', username)
                _db.set_setting('delug.DELUGE_PASSWORD', password)

        logger.info(f"Conectando ao Deluge: {username}@{host}")
        port = getattr(d, 'DELUGE_PORT', 58846)
        client = DelugeRPCClient(host, port, username, password)
        client.connect()
        return client
    except Exception as e:
        error_msg = str(e)
        if "Connection refused" in error_msg or "Errno 111" in error_msg or "target machine actively refused" in error_msg:
            logger.error(f"Deluge inacessível em {host}. Serviço parado ou bloqueado por firewall.")
        elif "Password does not match" in error_msg or "Authentication failed" in error_msg or "BadLoginError" in error_msg:
            logger.error(f"Senha incorreta para '{username}' no Deluge. Verifique o arquivo auth ou as configurações.")
        else:
            logger.error(f"Erro ao conectar ao Deluge: {e}")
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
                    # Extrair o hash do magnet link
                    info_hash = extrair_hash_magnet(magnet_link)

                    if info_hash:
                        # Verificar se o torrent já existe
                        existe, torrent_id_existente, nome_torrent = torrent_ja_existe(
                            client, info_hash)

                        if existe:
                            flash(
                                f'Este torrent já está na sua lista: {nome_torrent}', 'warning')
                        else:
                            # Adiciona o magnet link ao Deluge
                            client.call('core.add_torrent_magnet',
                                        magnet_link, {})
                            flash('Download adicionado com sucesso!', 'success')
                    else:
                        flash('Link magnet inválido ou mal formatado.', 'error')
                else:
                    flash('Erro ao conectar ao Deluge.', 'error')
            except Exception as e:
                # Verificar se é erro de torrent duplicado
                if 'already in session' in str(e).lower():
                    flash('Este torrent já está na sua lista de downloads.', 'warning')
                else:
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
            logger.info(f"Torrents raw data: {torrents}")
            
            for torrent_id, data in torrents.items():
                downloads.append({
                    'id': torrent_id.decode('utf-8') if isinstance(torrent_id, bytes) else torrent_id,
                    'name': data[b'name'].decode('utf-8') if isinstance(data.get(b'name'), bytes) else data.get(b'name', data.get('name')),
                    'progress': round(data[b'progress'], 2) if b'progress' in data else round(data.get('progress', 0), 2),
                    'state': data[b'state'].decode('utf-8') if isinstance(data.get(b'state'), bytes) else data.get(b'state', data.get('state'))
                })
            logger.info(f"Downloads formatted: {downloads}")
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


@delugeTorrent.route('/api/magnet', methods=['POST'])
def api_add_magnet():
    """
    Endpoint de API para receber links magnet de fontes externas (como extensões de navegador).
    Espera um JSON com o formato: {"magnetLink": "magnet:?xt=..."}
    Retorna um JSON com status de sucesso ou erro.
    """
    try:
        # Obter dados do JSON enviado
        data = request.get_json()

        # Verificar se o magnetLink está presente
        if not data or 'magnetLink' not in data:
            logger.error("Solicitação inválida: magnetLink não encontrado")
            return jsonify({
                "success": False,
                "message": "Link magnet não fornecido"
            }), 400

        magnet_link = data['magnetLink']

        # Verificar se é um pedido de teste de conexão
        if 'testMode' in data and data['testMode'] and magnet_link == 'magnet:?xt=urn:btih:TEST_CONNECTION':
            logger.info("Teste de conexão recebido")
            return jsonify({
                "success": True,
                "message": "Conexão teste bem-sucedida"
            }), 200

        # Verificar se o link é válido
        if not magnet_link.startswith('magnet:?'):
            logger.error(f"Link magnet inválido: {magnet_link}")
            return jsonify({
                "success": False,
                "message": "Link magnet inválido"
            }), 400

        # Conectar ao Deluge
        client = connect_deluge()
        if not client:
            logger.error("Falha ao conectar ao cliente Deluge")
            return jsonify({
                "success": False,
                "message": "Erro ao conectar ao Deluge"
            }), 500

        # Extrair o hash do magnet link
        info_hash = extrair_hash_magnet(magnet_link)

        if not info_hash:
            logger.error(
                f"Não foi possível extrair hash do magnet link: {magnet_link}")
            return jsonify({
                "success": False,
                "message": "Link magnet inválido ou mal formatado"
            }), 400

        # Verificar se o torrent já existe
        existe, torrent_id_existente, nome_torrent = torrent_ja_existe(
            client, info_hash)

        if existe:
            logger.info(
                f"Torrent já existe na sessão: {nome_torrent} ({torrent_id_existente})")
            return jsonify({
                "success": True,
                "message": f"Este torrent já está na sua lista: {nome_torrent}",
                "torrent_id": torrent_id_existente,
                "already_exists": True
            }), 200

        # Adicionar o torrent ao Deluge
        torrent_id = client.call('core.add_torrent_magnet', magnet_link, {})

        if torrent_id:
            logger.info(f"Torrent adicionado com sucesso: {torrent_id}")
            return jsonify({
                "success": True,
                "message": "Link magnet adicionado com sucesso",
                "torrent_id": torrent_id.decode('utf-8') if isinstance(torrent_id, bytes) else torrent_id,
                "already_exists": False
            }), 200
        else:
            logger.error("Falha ao adicionar torrent magnet")
            return jsonify({
                "success": False,
                "message": "Falha ao adicionar torrent"
            }), 500

    except Exception as e:
        logger.error(f"Erro ao processar link magnet via API: {e}")
        return jsonify({
            "success": False,
            "message": f"Erro: {str(e)}"
        }), 500


@delugeTorrent.route('/storage', methods=['GET'])
def get_storage():
    """
    Endpoint que retorna informações sobre o armazenamento do disco em JSON.
    """
    storage_info = get_disk_usage()
    return jsonify(storage_info), 200


# Testa a conexão com o Deluge ao iniciar (apenas no processo principal)
import os as _os
if _os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    _client = connect_deluge()
    if _client:
        logger.info("Deluge: conexão estabelecida com sucesso.")
    else:
        logger.warning("Deluge: falha na conexão inicial. Verifique as configurações.")
