
from flask import (
    Flask, render_template, jsonify, request,
    redirect, url_for, Response, stream_with_context,
    send_from_directory
)
import os
import time
import json
import zipfile
from werkzeug.utils import secure_filename
from io import BytesIO
import acceptance as start
import test_firmware as start_test_firmware
from routes_extra import extra_bp
from datetime import datetime

app = Flask(__name__)
app.register_blueprint(extra_bp)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run')
def run_page():
    return render_template('run.html')

@app.route('/tests')
def tests_page():
    return render_template('tests.html')

@app.route('/start1')
def start1_view():
    print(f"[{datetime.now()}] Запуск Acceptance теста через /start1")
    result = start.run()
    print(f"[{datetime.now()}] Acceptance тест завершен")
    return jsonify(result=result)

@app.route('/start3')
def start3_view():
    print(f"[{datetime.now()}] Запуск Firmware Upload теста через /start3")
    result = start_test_firmware.run()
    print(f"[{datetime.now()}] Firmware Upload тест завершен")
    return jsonify(result=result)


@app.route('/start1_progress')
def start1_progress():
    def generate():
        devices = start.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            yield f"data: {json.dumps({'progress':100,'done':True,'result':'Нет устройств'})}\n\n"
            return
        # Имитируем прогресс, так как run() выполнит тест
        for idx in range(1, total + 1):
            pct = int(idx / total * 100)
            yield f"data: {json.dumps({'progress':pct,'done':False})}\n\n"
            time.sleep(0.1)
        final = start.run()  # Выполняем тест один раз
        yield f"data: {json.dumps({'progress':100,'done':True,'result':final})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/start3_progress')
def start3_progress():
    def generate():
        devices, _ = start_test_firmware.load_firmware_config('config.txt')  # Извлекаем только devices
        total = len(devices)
        if total == 0:
            yield f"data: {json.dumps({'progress':100,'done':True,'result':'Нет устройств'})}\n\n"
            return
        # Имитируем прогресс, так как run() выполнит тест
        for idx in range(1, total + 1):
            pct = int(idx / total * 100)
            yield f"data: {json.dumps({'progress':pct,'done':False})}\n\n"
            time.sleep(0.1)
        final = start_test_firmware.run()  # Выполняем тест один раз
        yield f"data: {json.dumps({'progress':100,'done':True,'result':final})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/config', methods=['GET', 'POST'])
def config_page():
    config_path = os.path.join(os.getcwd(), 'config.txt')
    if request.method == 'POST':
        new_conf = request.form.get('config') or ''
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_conf)
        return redirect(url_for('config_page'))
    with open(config_path, 'r', encoding='utf-8') as f:
        conf = f.read()
    return render_template('config.html', config=conf)

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/logs')
def api_logs_list():
    logs_dir = os.path.join(os.getcwd(), 'logs')
    try:
        files = sorted(os.listdir(logs_dir))
    except FileNotFoundError:
        files = []
    return jsonify(files=[f for f in files if os.path.isfile(os.path.join(logs_dir, f))])

@app.route('/api/logs/<path:filename>')
def api_log_content(filename):
    logs_dir = os.path.join(os.getcwd(), 'logs')
    file_path = os.path.join(logs_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify(error='File not found'), 404
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif']:
        return jsonify(
            type='image',
            filename=filename,
            url=url_for('download_log', filename=filename)
        )
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return jsonify(
        type='text',
        filename=filename,
        content=content
    )

@app.route('/api/logs/download/<path:filename>')
def download_log(filename):
    logs_dir = os.path.join(os.getcwd(), 'logs')
    return send_from_directory(logs_dir, filename, as_attachment=True)

@app.route('/api/logs/delete/<path:filename>', methods=['DELETE'])
def delete_log(filename):
    logs_dir = os.path.join(os.getcwd(), 'logs')
    path = os.path.join(logs_dir, filename)
    if not os.path.isfile(path):
        return jsonify(success=False, error='Файл не найден'), 404
    try:
        os.remove(path)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/logs/download_all')
def download_all_logs():
    logs_dir = os.path.join(os.getcwd(), 'logs')
    files = [f for f in os.listdir(logs_dir) if os.path.isfile(os.path.join(logs_dir, f))]
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            full_path = os.path.join(logs_dir, file)
            zipf.write(full_path, arcname=secure_filename(file))
    zip_buffer.seek(0)
    return Response(
        zip_buffer.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': 'attachment; filename=logs.zip'}
    )

@app.route('/api/logs/analyze/<path:filename>', methods=['POST'])
def analyze_log(filename):
    logs_dir = os.path.join(os.getcwd(), 'logs')
    file_path = os.path.join(logs_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify(error='Файл не найден'), 404

    try:
        import log_analyzer
        answer = log_analyzer.analyze_file(file_path)
        return jsonify(answer=answer)
    except FileNotFoundError:
        return jsonify(error='Файл не найден'), 404
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/api/tests')
def api_tests_list():
    import tests_runner
    return jsonify(tests=tests_runner.list_tests())

@app.route('/api/tests/run', methods=['POST'])
def api_tests_run():
    import tests_runner
    data = request.get_json() or {}
    selected = data.get('tests', [])
    result = tests_runner.run_selected_tests(selected)
    return jsonify(result=result)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)