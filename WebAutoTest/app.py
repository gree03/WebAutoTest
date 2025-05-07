# app.py

from flask import (
    Flask, render_template, jsonify, request,
    redirect, url_for, Response, stream_with_context,
    send_from_directory
)
import os
import time
import json

import acceptance as start         # для Старт 1
import Regression as start2_module  # для Старт 2
import resultLog    # ваш модуль с функцией run()

app = Flask(__name__)

# ——— ваши существующие маршруты ———
# 
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run')
def run_page():
    return render_template('run.html')

@app.route('/start1')
def start1_view():
    return jsonify(result=start.run())

@app.route('/start2')
def start2_view():
    return jsonify(result=start2_module.run())

@app.route('/result')
def result_view():
    return jsonify(result=resultLog.run())

@app.route('/start1_progress')
def start1_progress():
    def generate():
        devices = start.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            yield f"data: {json.dumps({'progress':100,'done':True,'result':'Нет устройств'})}\n\n"
            return
        for idx, cfg in enumerate(devices, start=1):
            _ = start.handle_one(cfg)
            pct = int(idx / total * 100)
            yield f"data: {json.dumps({'progress':pct,'done':False})}\n\n"
            time.sleep(0.1)
        final = start.run()
        yield f"data: {json.dumps({'progress':100,'done':True,'result':final})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/start2_progress')
def start2_progress():
    def generate():
        devices = start2_module.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            yield f"data: {json.dumps({'progress':100,'done':True,'result':'Нет устройств'})}\n\n"
            return
        for idx, cfg in enumerate(devices, start=1):
            _ = start2_module.handle_one(cfg)
            pct = int(idx / total * 100)
            yield f"data: {json.dumps({'progress':pct,'done':False})}\n\n"
            time.sleep(0.1)
        final = start2_module.run()
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


# ——— Логи и API для них ———

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
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return jsonify(filename=filename, content=content)

# Новый маршрут для скачивания файла
@app.route('/api/logs/download/<path:filename>')
def download_log(filename):
    logs_dir = os.path.join(os.getcwd(), 'logs')
    return send_from_directory(logs_dir, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
