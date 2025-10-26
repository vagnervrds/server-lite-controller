# blueprint_magnet.py
from flask import Blueprint, render_template, jsonify, request
import urllib.request
import urllib.error
import re
import ssl
import gzip
import json


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

        with urllib.request.urlopen(requisicao, context=contexto_ssl, timeout=15) as resposta:
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
