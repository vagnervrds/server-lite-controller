import os
import fnmatch
import shutil  # Adicionado para operações de pasta não vazias
from flask import Flask, render_template, jsonify, request, send_from_directory, abort, Blueprint
from werkzeug.utils import secure_filename

from utils import ler_settings
fileManager = Blueprint('fileManager', __name__)

# Configurações
settings = ler_settings()
DOWNLOAD_DIR = settings.DOWNLOAD_DIR

# Adicione mais conforme necessário
ALLOWED_EXTENSIONS = set(
    ['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar', 'mp3', 'mp4', 'doc', 'docx', 'xls', 'xlsx'])


# Função para verificar extensões permitidas
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Função para listar arquivos e pastas
def list_directory(req_path):
    abs_path = os.path.join(DOWNLOAD_DIR, req_path)

    if not os.path.exists(abs_path):
        abort(404, description="Caminho não encontrado")

    if os.path.isfile(abs_path):
        return jsonify({'type': 'file', 'name': os.path.basename(abs_path)})

    items = []
    for entry in os.listdir(abs_path):
        entry_path = os.path.join(abs_path, entry)
        if os.path.isdir(entry_path):
            items.append({'type': 'folder', 'name': entry})
        else:
            items.append({'type': 'file', 'name': entry})

    return jsonify({'type': 'folder', 'name': os.path.basename(abs_path) or 'Raiz', 'items': items})


# Rota para a página principal
@fileManager.route('/', methods=['GET', 'POST'])
def home():
    return render_template('filemanager.html')


# API para obter o conteúdo de um diretório
@fileManager.route('/api/list', methods=['GET'])
def api_list():
    req_path = request.args.get('path', '')
    return list_directory(req_path)


# API para fazer upload de arquivos múltiplos
@fileManager.route('/api/upload', methods=['POST'])
def api_upload():
    current_path = request.form.get('current_path', '')
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'}), 400

    upload_path = os.path.join(DOWNLOAD_DIR, current_path)
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    uploaded_files = []
    failed_files = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            try:
                file.save(os.path.join(upload_path, filename))
                uploaded_files.append(filename)
            except Exception as e:
                failed_files.append(
                    {'filename': file.filename, 'error': str(e)})
        else:
            failed_files.append(
                {'filename': file.filename, 'error': 'Tipo de arquivo não permitido'})

    message = ''
    if uploaded_files:
        message += f"Sucesso: {', '.join(uploaded_files)}. "
    if failed_files:
        failed_details = '; '.join(
            [f"{f['filename']} ({f['error']})" for f in failed_files])
        message += f"Falha: {failed_details}."

    status = 200 if uploaded_files else 400
    return jsonify({'success': len(uploaded_files) > 0, 'message': message}), status


# API para criar uma nova pasta
@fileManager.route('/api/create_folder', methods=['POST'])
def api_create_folder():
    current_path = request.form.get('current_path', '')
    folder_name = request.form.get('folder_name', '').strip()
    if folder_name:
        folder_name = secure_filename(folder_name)
        new_folder_path = os.path.join(
            DOWNLOAD_DIR, current_path, folder_name)
        try:
            # Adicionado exist_ok para evitar erros se a pasta já existir
            os.makedirs(new_folder_path, exist_ok=True)
            return jsonify({'success': True, 'message': 'Pasta criada com sucesso'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Erro ao criar pasta: {e}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Nome da pasta inválido'}), 400


# API para deletar arquivos/pastas múltiplos
@fileManager.route('/api/delete_multiple', methods=['POST'])
def api_delete_multiple():
    data = request.get_json()
    if not data or 'targets' not in data:
        return jsonify({'success': False, 'message': 'Nenhum alvo especificado'}), 400

    current_path = data.get('current_path', '')
    targets = data.get('targets', [])

    if not isinstance(targets, list):
        return jsonify({'success': False, 'message': 'Alvos inválidos'}), 400

    upload_path = os.path.join(DOWNLOAD_DIR, current_path)
    if not os.path.exists(upload_path):
        return jsonify({'success': False, 'message': 'Caminho atual não encontrado'}), 404

    deleted_files = []
    failed_files = []

    for target in targets:
        target_path = os.path.join(upload_path, target)
        try:
            if os.path.isfile(target_path):
                os.remove(target_path)
                deleted_files.append(target)
            elif os.path.isdir(target_path):
                # Usando rmtree para remover pastas e seu conteúdo
                shutil.rmtree(target_path)
                deleted_files.append(target)
            else:
                failed_files.append(
                    {'target': target, 'error': 'Alvo não encontrado'})
        except Exception as e:
            failed_files.append({'target': target, 'error': str(e)})

    message = ''
    if deleted_files:
        message += f"Itens deletados com sucesso: {', '.join(deleted_files)}. "
    if failed_files:
        failed_details = '; '.join(
            [f"{f['target']} ({f['error']})" for f in failed_files])
        message += f"Falha na deleção de alguns itens: {failed_details}."

    status = 200 if deleted_files else 400
    return jsonify({'success': len(deleted_files) > 0, 'message': message}), status


# API para pesquisar arquivos e pastas
@fileManager.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify({'success': False, 'message': 'Consulta de pesquisa vazia'}), 400

    matches = []
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        rel_root = os.path.relpath(root, DOWNLOAD_DIR)
        # Procurar em pastas
        for dir_name in dirs:
            if fnmatch.fnmatch(dir_name.lower(), f'*{query}*'):
                path = os.path.join(
                    rel_root, dir_name) if rel_root != '.' else dir_name
                matches.append(
                    {'type': 'folder', 'name': dir_name, 'path': path})
        # Procurar em arquivos
        for file_name in files:
            if fnmatch.fnmatch(file_name.lower(), f'*{query}*'):
                path = os.path.join(
                    rel_root, file_name) if rel_root != '.' else file_name
                matches.append(
                    {'type': 'file', 'name': file_name, 'path': path})

    return jsonify({'success': True, 'results': matches})


# Rota para download de arquivos
@fileManager.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
