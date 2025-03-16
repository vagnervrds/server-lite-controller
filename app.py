from urllib.parse import unquote, urlparse
import os
from flask import Flask, render_template, request, jsonify
import threading
import requests
from deluge_torrent import delugeTorrent  # Importe o blueprint
from file_manager import fileManager

import secrets
# Configurar o logger
from logger_config import setup_logger
from utils import ler_settings
logger = setup_logger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.register_blueprint(delugeTorrent, url_prefix='/torrent')
app.register_blueprint(fileManager, url_prefix='/filemanager')

settings = ler_settings()

DOWNLOAD_DIR = settings.DOWNLOAD_DIR


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/desligar", methods=["POST"])
def desligar():
    os.system("/sbin/shutdown -h now")
    return "Desligando o servidor..."


@app.route("/reiniciar", methods=["POST"])
def reiniciar():
    os.system("/sbin/reboot")
    return "Reiniciando o servidor..."


# Alterado para usar um dicionário com IDs únicos
downloads = {}
# download_id_counter = 1  # Contador para IDs únicos


@app.route("/downloads", methods=["GET"])
def downloads_page():
    return render_template("downloads.html", downloads=downloads)


@app.route("/download", methods=["POST"])
def start_download():
    url = request.form.get("url")
    folder = request.form.get("folder", "").strip()

    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    filename = unquote(filename)
    download_dir = os.path.join(
        DOWNLOAD_DIR, folder) if folder else DOWNLOAD_DIR
    os.makedirs(download_dir, exist_ok=True)
    filepath = os.path.join(download_dir, filename)

    download_id = len(downloads) + 1
    print("iniciando dolwoad", download_id)

    def download_file():
        try:
            with requests.get(url, stream=True) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded_size = 0
                with open(filepath, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if not downloads[download_id]["active"]:
                            downloads[download_id]["status"] = "Pausado"
                            return

                        if chunk:
                            file.write(chunk)
                            downloaded_size += len(chunk)
                            downloads[download_id]["progress"] = int(
                                (downloaded_size / total_size) * 100) if total_size else 0

            downloads[download_id]["progress"] = 100
            downloads[download_id]["status"] = "Concluído"
        except Exception as e:
            downloads[download_id]["status"] = f"Erro: {e}"

    downloads[download_id] = {
        "id": download_id,
        "url": url,
        "progress": 0,
        "status": "Baixando arquivo...",
        "filepath": filepath,
        "active": True
    }

    thread = threading.Thread(target=download_file)
    thread.start()

    return jsonify({"message": "Download iniciado", "id": download_id, "url": url})


@app.route("/downloads/progress", methods=["GET"])
def downloads_progress():
    return jsonify(list(downloads.values()))


@app.route("/downloads/control", methods=["POST"])
def control_download():
    download_id = request.json.get("id")
    print("apagar", download_id)
    action = request.json.get("action")

    if download_id not in downloads:
        return jsonify({"error": "Download não encontrado"}), 404

    if action == "pause":
        downloads[download_id]["active"] = False
        downloads[download_id]["status"] = "Pausado"
    elif action == "resume":
        downloads[download_id]["active"] = True
        downloads[download_id]["status"] = "Retomando"
        thread = threading.Thread(
            target=start_download, args=(downloads[download_id]["url"],))
        thread.start()
    elif action == "delete":
        delete_files = request.json.get("delete_files", False)
        if delete_files and os.path.exists(downloads[download_id]["filepath"]):
            os.remove(downloads[download_id]["filepath"])
        del downloads[download_id]
    else:
        return jsonify({"error": "Ação inválida"}), 400

    return jsonify({"message": f"Ação '{action}' executada para download {download_id}"})


if __name__ == "__main__":
    logger.info("Iniciando o servidor Flask.")
    app.run(host="0.0.0.0", port=5010, debug=True)
