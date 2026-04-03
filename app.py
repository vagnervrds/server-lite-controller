from blueprint_magnet import magnet_bp
from urllib.parse import unquote, urlparse
import os
import json
from flask import Flask, render_template, request, jsonify
import threading
import requests
from deluge_torrent import delugeTorrent
from file_manager import fileManager
from monitor import monitorBlueP

import secrets
from logger_config import setup_logger
import database as db
from utils import ler_settings

logger = setup_logger(__name__)

app = Flask(__name__)
app.register_blueprint(magnet_bp)
app.secret_key = secrets.token_hex(16)
app.register_blueprint(delugeTorrent, url_prefix="/torrent")
app.register_blueprint(monitorBlueP, url_prefix="/monitor")
app.register_blueprint(fileManager, url_prefix="/filemanager")


def get_download_dir():
    settings = ler_settings()
    return settings.DOWNLOAD_DIR if settings else "/mnt/dietpi_userdata/downloads"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config", methods=["GET"])
def config_page():
    return render_template("config.html")


@app.route("/api/config", methods=["GET"])
def api_config_get():
    settings = ler_settings()
    config_data = {"DOWNLOAD_DIR": settings.DOWNLOAD_DIR if settings else ""}
    return jsonify(config_data)


@app.route("/config", methods=["POST"])
def config_save():
    from utils import salvar_settings_dict

    new_dir = request.form.get("download_dir")
    if new_dir:
        success = salvar_settings_dict({"DOWNLOAD_DIR": new_dir})
        if success:
            return jsonify({"message": "Configurações salvas com sucesso!"})
        else:
            return jsonify({"error": "Erro ao salvar as configurações."}), 500
    return jsonify({"error": "Diretório não fornecido"}), 400


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
    download_dir = (
        os.path.join(get_download_dir(), folder) if folder else get_download_dir()
    )
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
                            downloads[download_id]["progress"] = (
                                int((downloaded_size / total_size) * 100)
                                if total_size
                                else 0
                            )

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
        "active": True,
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
            target=start_download, args=(downloads[download_id]["url"],)
        )
        thread.start()
    elif action == "delete":
        delete_files = request.json.get("delete_files", False)
        if delete_files and os.path.exists(downloads[download_id]["filepath"]):
            os.remove(downloads[download_id]["filepath"])
        del downloads[download_id]
    else:
        return jsonify({"error": "Ação inválida"}), 400

    return jsonify(
        {"message": f"Ação '{action}' executada para download {download_id}"}
    )


def _log_deluge_info():
    """Lê e loga as credenciais do Deluge (daemon e web UI) encontradas no sistema."""
    auth_candidates = [
        "/mnt/dietpi_userdata/deluge/auth",
        os.path.expanduser("~/.config/deluge/auth"),
    ]
    web_candidates = [
        "/mnt/dietpi_userdata/deluge/web.conf",
        os.path.expanduser("~/.config/deluge/web.conf"),
    ]

    logger.info("=" * 55)
    logger.info("  CREDENCIAIS DO DELUGE")
    logger.info("=" * 55)

    # --- Daemon RPC (auth file) ---
    found_auth = False
    for path in auth_candidates:
        if not os.path.exists(path):
            continue
        logger.info(f"Arquivo auth encontrado: {path}")
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":")
                    if len(parts) >= 3:
                        user, pwd, level = parts[0], parts[1], parts[2]
                        logger.info(
                            f"  [daemon] usuario={user}  senha={pwd}  nivel={level}"
                        )
                    elif len(parts) == 2:
                        user, pwd = parts[0], parts[1]
                        logger.info(f"  [daemon] usuario={user}  senha={pwd}")
            found_auth = True
        except Exception as e:
            logger.warning(f"  Não foi possível ler {path}: {e}")
        break

    if not found_auth:
        logger.warning("  Arquivo auth do Deluge não encontrado.")

    # --- Web UI (web.conf) ---
    found_web = False
    for path in web_candidates:
        if not os.path.exists(path):
            continue
        logger.info(f"Arquivo web.conf encontrado: {path}")
        try:
            with open(path, "r") as f:
                web_conf = json.load(f)
            pwd_hash = (
                web_conf.get("pwd_sha1")
                or web_conf.get("pwd_md5")
                or "(não encontrado)"
            )
            logger.info(f"  [web UI] senha (hash): {pwd_hash}")
            logger.info(
                "  [web UI] usuario: (sem usuario — apenas senha no login da web UI)"
            )
            found_web = True
        except Exception as e:
            logger.warning(f"  Não foi possível ler {path}: {e}")
        break

    if not found_web:
        logger.info(
            "  web.conf não encontrado — senha padrão da web UI provavelmente é 'deluge'."
        )

    logger.info("=" * 55)


if __name__ == "__main__":
    # WERKZEUG_RUN_MAIN só existe no processo filho do reloader.
    # Assim o bloco de startup roda uma única vez, no processo principal.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        logger.info("Iniciando o servidor Flask.")
        _log_deluge_info()
    app.run(host="0.0.0.0", port=5010, debug=True)
