from flask import (
    Blueprint, render_template, jsonify, request,
    send_from_directory, Response, stream_with_context
)
import os
import time
import json
from werkzeug.utils import secure_filename
from PIL import Image

extra_bp = Blueprint('extra', __name__)

# Корневой каталог для прошивок
FIRMWARE_ROOT = os.path.join(os.getcwd(), 'firmware')

# Маршрут на страницу управления прошивками
@extra_bp.route('/ser', endpoint='ser')
def ser_page():
    return render_template('ser.html')

# API: список папок-версий в firmware/
@extra_bp.route('/api/firmware/versions')
def list_versions():
    try:
        versions = [
            d for d in os.listdir(FIRMWARE_ROOT)
            if os.path.isdir(os.path.join(FIRMWARE_ROOT, d))
        ]
    except FileNotFoundError:
        versions = []
    return jsonify({'versions': versions})

# API: создать новую папку-версию
@extra_bp.route('/api/firmware/versions/create', methods=['POST'])
def create_version():
    data = request.get_json() or {}
    version = data.get('version', '').strip()
    if not version:
        return jsonify({'error': 'Название версии не указано'}), 400
    path = os.path.join(FIRMWARE_ROOT, version)
    try:
        os.makedirs(path, exist_ok=False)
        return jsonify({'success': True, 'version': version}), 201
    except FileExistsError:
        return jsonify({'error': 'Версия уже существует'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: список файлов в указанной версии
@extra_bp.route('/api/firmware/<version>')
def list_files(version):
    path = os.path.join(FIRMWARE_ROOT, version)
    if not os.path.isdir(path):
        return jsonify({'error': 'Версия не найдена'}), 404
    files = os.listdir(path)
    return jsonify({'files': files})

# API: загрузка файла в указанную версию
@extra_bp.route('/api/firmware/<version>/upload', methods=['POST'])
def upload_file(version):
    path = os.path.join(FIRMWARE_ROOT, version)
    os.makedirs(path, exist_ok=True)
    if 'file' not in request.files:
        return jsonify({'error': 'Нет поля file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Нет выбранного файла'}), 400

    # Если это изображение, сохраняем как info.png или info1.png, info2.png и т.д.
    if file.mimetype.startswith('image/'):
        try:
            img = Image.open(file.stream)
            img = img.convert('RGBA')
            base, ext = 'info', '.png'
            filename = f"{base}{ext}"
            counter = 1
            # Найти уникальное имя
            while os.path.exists(os.path.join(path, filename)):
                filename = f"{base}{counter}{ext}"
                counter += 1
            save_path = os.path.join(path, filename)
            img.save(save_path, 'PNG')
        except Exception as e:
            return jsonify({'error': f'Ошибка конвертации изображения: {e}'}), 500
    else:
        # Для других файлов сохраняем под оригинальным именем
        filename = secure_filename(file.filename)
        file.save(os.path.join(path, filename))

    return jsonify({'success': True, 'filename': filename})

# Скачать один файл прошивки
@extra_bp.route('/firmware/<version>/<filename>')
def download_file(version, filename):
    directory = os.path.join(FIRMWARE_ROOT, version)
    return send_from_directory(directory, filename, as_attachment=True)

# API: удаление файла прошивки
@extra_bp.route('/api/firmware/<version>/delete/<filename>', methods=['DELETE'])
def delete_file(version, filename):
    path = os.path.join(FIRMWARE_ROOT, version, filename)
    try:
        os.remove(path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== TEST RUN ROUTES =====================

@extra_bp.route('/start2_progress')
def start2_progress():
    """Run Regression test with progress via Server-Sent Events."""
    import Regression as regression

    def generate():
        devices = regression.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            yield f"data: {json.dumps({'progress': 100, 'done': True, 'result': 'Нет устройств'})}\n\n"
            return
        for idx in range(1, total + 1):
            pct = int(idx / total * 100)
            yield f"data: {json.dumps({'progress': pct, 'done': False})}\n\n"
            time.sleep(0.1)
        final = regression.run()
        yield f"data: {json.dumps({'progress': 100, 'done': True, 'result': final})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

