# blueprint_magnet.py
from flask import Blueprint, render_template, jsonify, request
import urllib.request
import urllib.error
import urllib.parse
import re
import ssl
import gzip
import json
from logger_config import setup_logger

logger = setup_logger(__name__)


# Criar o blueprint
magnet_bp = Blueprint('magnet', __name__,
                      template_folder='templates',
                      static_folder='static',
                      url_prefix='/magnet')


def fazer_requisicao_realista(url):
    """
    Faz uma requisição HTTP realista simulando um navegador
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

    try:
        contexto_ssl = ssl.create_default_context()
        contexto_ssl.check_hostname = False
        contexto_ssl.verify_mode = ssl.CERT_NONE

        requisicao = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(requisicao, context=contexto_ssl, timeout=90) as resposta:
            conteudo = resposta.read()

            encoding = resposta.headers.get('Content-Encoding', '').lower()

            if encoding == 'gzip':
                conteudo = gzip.decompress(conteudo)
            elif encoding == 'deflate':
                import zlib
                try:
                    conteudo = zlib.decompress(conteudo)
                except:
                    conteudo = zlib.decompress(conteudo, -zlib.MAX_WBITS)

            try:
                html = conteudo.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    html = conteudo.decode('latin-1')
                except:
                    html = conteudo.decode('iso-8859-1')

            return html

    except urllib.error.HTTPError as e:
        return None, f"Erro HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"Erro de conexão: {e.reason}"
    except Exception as e:
        return None, f"Erro inesperado: {str(e)}"


def extrair_magnet_links(html):
    """
    Extrai todos os magnet links do HTML
    """
    padrao = r'magnet:\?xt=urn:btih:[a-f0-9A-F]+[^\s"<>]*'
    magnet_urls = re.findall(padrao, html, re.IGNORECASE)

    magnet_urls_unicos = []
    for url in magnet_urls:
        if url not in magnet_urls_unicos:
            magnet_urls_unicos.append(url)

    return magnet_urls_unicos


def extrair_titulo_magnet(magnet_link):
    """
    Tenta extrair o título do magnet link a partir do parâmetro dn (display name)
    """
    try:
        match = re.search(r'[&?]dn=([^&]+)', magnet_link)
        if match:
            titulo = match.group(1)
            # Decodificar URL encoding
            titulo = urllib.parse.unquote(titulo)
            # Substituir pontos e underscores por espaços
            titulo = titulo.replace('.', ' ').replace('_', ' ')
            return titulo
        else:
            # Se não encontrar título, retorna parte do hash
            hash_match = re.search(
                r'btih:([a-f0-9A-F]+)', magnet_link, re.IGNORECASE)
            if hash_match:
                return f"Torrent {hash_match.group(1)[:8]}..."
            return "Sem título"
    except:
        return "Sem título"


def _extrair_hash(magnet_link):
    """Extrai o info_hash de um magnet link (hex ou base32 → hex)."""
    match = re.search(r'btih:([a-f0-9]{40})', magnet_link, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    match = re.search(r'btih:([A-Z2-7]{32})', magnet_link, re.IGNORECASE)
    if match:
        import base64
        try:
            return base64.b32decode(match.group(1).upper()).hex()
        except Exception:
            return match.group(1).lower()
    return None


def _resolver_nome_via_deluge(magnet_link, info_hash):
    """
    Tenta obter o nome do torrent via Deluge:
    1. Verifica se o hash já está na sessão do Deluge.
    2. Tenta core.get_torrent_info() para buscar metadados do magnet via DHT.
    Retorna o nome (str) ou None.
    """
    try:
        from deluge_torrent import connect_deluge
        client = connect_deluge()
        if not client:
            return None

        # 1. Torrent já está na sessão?
        torrents = client.call('core.get_torrents_status', {}, ['name'])
        for tid, data in torrents.items():
            tid_str = tid.decode('utf-8') if isinstance(tid, bytes) else tid
            if tid_str.lower() == info_hash:
                name = data.get(b'name') or data.get('name', b'')
                if isinstance(name, bytes):
                    name = name.decode('utf-8', errors='replace')
                if name:
                    logger.info(f"Nome resolvido via sessão Deluge: {name}")
                    return name

        # 2. Busca metadados do magnet via DHT (get_torrent_info)
        try:
            info = client.call('core.get_torrent_info', magnet_link)
            if info:
                name = info.get(b'name') or info.get('name', b'')
                if isinstance(name, bytes):
                    name = name.decode('utf-8', errors='replace')
                if name:
                    logger.info(f"Nome resolvido via get_torrent_info: {name}")
                    return name
        except Exception as e:
            logger.debug(f"get_torrent_info não disponível: {e}")

    except Exception as e:
        logger.warning(f"Erro ao resolver nome via Deluge: {e}")

    return None


@magnet_bp.route('/resolve-title', methods=['POST'])
def resolve_title():
    """
    Recebe um magnet link e tenta retornar o nome real do torrent via Deluge.
    Usado pelo frontend para enriquecer links que têm apenas o hash como título.
    """
    data = request.get_json() or {}
    magnet_link = data.get('magnet', '').strip()

    if not magnet_link:
        return jsonify({'nome': None})

    info_hash = _extrair_hash(magnet_link)
    if not info_hash:
        return jsonify({'nome': None})

    nome = _resolver_nome_via_deluge(magnet_link, info_hash)
    return jsonify({'nome': nome})


@magnet_bp.route('/')
def index():
    """
    Rota principal - exibe o formulário
    """
    return render_template('magnet.html')


@magnet_bp.route('/extrair', methods=['POST'])
def extrair():
    """
    Rota para extrair magnet links de uma URL
    """
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({
                'sucesso': False,
                'erro': 'URL não pode estar vazia'
            }), 400

        # Adicionar protocolo se não tiver
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Fazer requisição
        resultado = fazer_requisicao_realista(url)

        if isinstance(resultado, tuple):
            html, erro = resultado
            return jsonify({
                'sucesso': False,
                'erro': erro
            }), 500
        else:
            html = resultado

        # Extrair magnet links
        magnet_links = extrair_magnet_links(html)

        if not magnet_links:
            return jsonify({
                'sucesso': False,
                'erro': 'Nenhum magnet link encontrado na página'
            }), 404

        # Preparar lista de magnet links com títulos
        links_com_titulo = []
        for link in magnet_links:
            titulo = extrair_titulo_magnet(link)
            links_com_titulo.append({
                'titulo': titulo,
                'link': link
            })

        return jsonify({
            'sucesso': True,
            'total': len(magnet_links),
            'links': links_com_titulo
        })

    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': f'Erro ao processar requisição: {str(e)}'
        }), 500


print("Blueprint 'magnet' carregado.")

# Exemplo de como registrar o blueprint em uma aplicação Flask
"""
# app.py
from flask import Flask
from blueprint_magnet import magnet_bp

app = Flask(__name__)
app.register_blueprint(magnet_bp)

if __name__ == '__main__':
    app.run(debug=True)
"""
