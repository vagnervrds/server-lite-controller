from urllib.parse import unquote, urlparse
import os
from flask import Flask, render_template, request, jsonify
import threading
import requests
from deluge_torrent import delugeTorrent  # Importe o blueprint
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.register_blueprint(delugeTorrent, url_prefix='/torrent')


DOWNLOAD_DIR = "/mnt/dietpi_userdata/downloads"
downloads = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/downloads", methods=["GET"])
def downloads_page():
    return render_template("downloads.html", downloads=downloads)


@app.route("/download", methods=["POST"])
def start_download():
    url = request.form.get("url")
    folder = request.form.get("folder", "").strip()
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    else:  # HTTP/HTTPS link
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        filename = unquote(filename)
        download_dir = os.path.join(
            DOWNLOAD_DIR, folder) if folder else DOWNLOAD_DIR
        os.makedirs(download_dir, exist_ok=True)
        filepath = os.path.join(download_dir, filename)

        def download_file():
            try:
                with requests.get(url, stream=True) as response:
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0
                    with open(filepath, "wb") as file:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                file.write(chunk)
                                downloaded_size += len(chunk)
                                for d in downloads:
                                    if d["url"] == url:
                                        d["progress"] = int(
                                            (downloaded_size / total_size) * 100) if total_size else 0
            finally:
                for d in downloads:
                    if d["url"] == url:
                        d["progress"] = 100
                        d["status"] = "Concluído"
                        break

        downloads.append({"url": url, "progress": 0,
                         "status": "Baixando arquivo..."})
        thread = threading.Thread(target=download_file)
        thread.start()
        return jsonify({"message": "Download iniciado", "url": url})


@app.route("/torrent/<action>", methods=["POST"])
def manage_torrent(action):
    torrent_id = request.json.get("torrent_id")
    if not torrent_id:
        return jsonify({"error": "ID do torrent não fornecido"}), 400

    try:
        if action == "pause":
            client.call("core.pause_torrent", [torrent_id])
        elif action == "resume":
            client.call("core.resume_torrent", [torrent_id])
        elif action == "delete":
            client.call("core.remove_torrent", torrent_id, True)
        return jsonify({"message": f"Torrent {action} com sucesso"})
    except Exception as e:
        return jsonify({"error": f"Erro ao executar {action}: {str(e)}"}), 500


@app.route("/downloads/progress", methods=["GET"])
def downloads_progress():
    try:
        torrent_status = client.call("core.get_torrents_status", {}, [
                                     "name", "progress", "state"])
        for torrent_id, status in torrent_status.items():
            downloads.append({
                "url": status["name"],
                "progress": status["progress"],
                "status": status["state"]
            })
    except Exception as e:
        return jsonify({"error": f"Erro ao obter progresso dos torrents: {str(e)}"}), 500
    return jsonify(downloads)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
