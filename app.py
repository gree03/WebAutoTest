# app.py
# Мега тестовое изменение
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
import resultLog
from routes_extra import extra_bp
from datetime import datetime
from progTest.screenshot import run as screenshot_run
from progTest.ParsProshivka import get_device_info as version_run

app = Flask(__name__)
app.register_blueprint(extra_bp)

# Доступные автотесты в папке progTest
AVAILABLE_TESTS = {
    'screenshot': screenshot_run,
    'version': version_run,
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run')
def run_page():
    return render_template('run.html')

# Страница выбора автотестов
@app.route('/select-tests')
def select_tests():
    return render_template('select_tests.html', tests=AVAILABLE_TESTS.keys())

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

@app.route('/result')
def result_view():
    return jsonify(result=resultLog.run())

# Запуск выбранных автотестов
@app.route('/api/run-tests', methods=['POST'])
def api_run_tests():
    data = request.get_json() or {}
    selected = data.get('tests', [])
    selected_funcs = {t: AVAILABLE_TESTS[t] for t in selected if t in AVAILABLE_TESTS}
    if not selected_funcs:
        return jsonify(result='Нет выбранных тестов')

    devices = start.load_device_configs('config.txt')
    results = []
    for cfg in devices:
        ip = cfg.get('IP_CAMERA', '')
        login = cfg.get('LOGIN', '')
        password = cfg.get('PASSWORD', '')
        device_res = {}
        for name, func in selected_funcs.items():
            try:
                if name == 'screenshot':
                    r = func(ip, login, password)
                    device_res['screenshot'] = r.get('success_rate')
                elif name == 'version':
                    r = func(ip, login, password)
                    device_res['version'] = r
            except Exception as e:
                device_res[name] = f'Ошибка: {e}'
        results.append((cfg, device_res))

    lines = []
    for cfg, res in results:
        cfg_line = " ".join(f"{k}={v}" for k, v in cfg.items())
        lines.append(cfg_line)
        for k, v in res.items():
            lines.append(f"{k}: {v}")
        lines.append('')

    log_text = "\n".join(lines).strip()
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"logcustom_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(log_text)

    return jsonify(result=log_text)

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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)