from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import threading
import time
import json
import os
import importlib
from datetime import datetime
import acceptance
import tests_runner

router = APIRouter()

class TestRunner:
    def __init__(self):
        self.thread = None
        self.stop_event = threading.Event()
        self.progress = 0
        self.result_lines = []
        self.done = False
        self.prefix = ""

    def start(self, mode: str, selected=None):
        if self.thread and self.thread.is_alive():
            return False
        self.stop_event.clear()
        self.progress = 0
        self.result_lines = []
        self.done = False
        self.prefix = "logacceptance" if mode == "acceptance" else mode
        self.thread = threading.Thread(target=self._run, args=(mode, selected), daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
            return True
        return False

    def _append_result(self, cfg, result_dict):
        line = " ".join(f"{k}={v}" for k, v in cfg.items())
        self.result_lines.append(line)
        for name, value in result_dict.items():
            self.result_lines.append(f"{name}: {value}")
        self.result_lines.append("")

    def _run_acceptance(self):
        devices = acceptance.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            self.result_lines.append('Нет устройств в config.txt')
            self.progress = 100
            return
        for idx, cfg in enumerate(devices):
            if self.stop_event.is_set():
                break
            result = acceptance.handle_one(cfg)
            self._append_result(cfg, result)
            self.progress = int((idx + 1) / total * 100)

    def _run_regression(self):
        tests = tests_runner._discover_tests()
        devices = acceptance.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            self.result_lines.append('Нет устройств в config.txt')
            self.progress = 100
            return
        for idx, cfg in enumerate(devices):
            if self.stop_event.is_set():
                break
            ip = cfg.get('IP_CAMERA', '')
            login = cfg.get('LOGIN', '')
            password = cfg.get('PASSWORD', '')
            results = {}
            for name, mod in tests.items():
                module = importlib.import_module(mod[0])
                func = getattr(module, mod[1])
                try:
                    results[name] = func(ip, login, password)
                except Exception as e:
                    results[name] = f'Ошибка: {e}'
            self._append_result(cfg, results)
            self.progress = int((idx + 1) / total * 100)

    def _run_selected(self, selected):
        tests = tests_runner.TEST_MAP
        devices = acceptance.load_device_configs('config.txt')
        total = len(devices)
        if total == 0:
            self.result_lines.append('Нет устройств в config.txt')
            self.progress = 100
            return
        for idx, cfg in enumerate(devices):
            if self.stop_event.is_set():
                break
            ip = cfg.get('IP_CAMERA', '')
            login = cfg.get('LOGIN', '')
            password = cfg.get('PASSWORD', '')
            results = {}
            for name in selected:
                mod = tests.get(name)
                if not mod:
                    results[name] = 'неизвестный тест'
                    continue
                module = importlib.import_module(mod[0])
                func = getattr(module, mod[1])
                try:
                    results[name] = func(ip, login, password)
                except Exception as e:
                    results[name] = f'Ошибка: {e}'
            self._append_result(cfg, results)
            self.progress = int((idx + 1) / total * 100)

    def _run(self, mode, selected):
        if mode == 'acceptance':
            self._run_acceptance()
        elif mode == 'regression':
            self._run_regression()
        elif mode == 'selected':
            self._run_selected(selected or [])
        self.done = True

    def _log_text(self):
        return "\n".join(self.result_lines).strip()

    def _save_log(self):
        text = self._log_text()
        os.makedirs('logs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join('logs', f'{self.prefix}_{timestamp}.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return text

    def stream(self):
        while not self.done:
            data = json.dumps({'progress': self.progress, 'done': False})
            yield f'data: {data}\n\n'
            time.sleep(0.5)
        text = self._save_log()
        data = json.dumps({'progress': 100, 'done': True, 'result': text})
        yield f'data: {data}\n\n'

runner = TestRunner()

@router.get('/start1_progress')
async def start1_progress():
    runner.start('acceptance')
    return StreamingResponse(runner.stream(), media_type='text/event-stream')

@router.get('/start2_progress')
async def start2_progress():
    runner.start('regression')
    return StreamingResponse(runner.stream(), media_type='text/event-stream')

@router.post('/api/tests/run_progress')
async def run_tests_progress(request: Request):
    data = await request.json()
    selected = data.get('tests', [])
    runner.start('selected', selected)
    return StreamingResponse(runner.stream(), media_type='text/event-stream')

@router.post('/stop')
async def stop():
    stopped = runner.stop()
    return {'stopped': stopped}
