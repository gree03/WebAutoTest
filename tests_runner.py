""" Это тот саммый продвиннутый запуск

1. `_discover_tests()` — находит все `.py`-файлы в `progTest`, где есть функция `run` или аналог, добавляет их в словарь `TEST_MAP`.(По данной причине любой файл теста должна быть функция run)

2. `list_tests()` — возвращает список найденных тестов.

3. `run_selected_tests(selected)` — загружает устройства из `config.txt`, отфильтровывает недоступные, запускает выбранные тесты на доступных IP, сохраняет лог в файл, возвращает текст с результатами.
"""


import os
from datetime import datetime
import importlib
from typing import Dict, List
import Regression as regression
from ping_utils import filter_reachable_devices
from syslog_server import start_syslog_server, stop_syslog_server


def _discover_tests() -> Dict[str, tuple]:
    """Dynamically discover tests inside ``progTest`` folder.

    A test is a module that contains a ``run`` function.  Some modules have
    specific entry points, so we handle them here as well.
    """
    tests: Dict[str, tuple] = {}
    base = 'progTest'
    for file in os.listdir(base):
        if not file.endswith('.py') or file.startswith('_'):
            continue
        name = os.path.splitext(file)[0]
        module_name = f'{base}.{name}'
        module = importlib.import_module(module_name)
        if hasattr(module, 'run'):
            tests[name] = (module_name, 'run')
        elif hasattr(module, 'get_device_info'):
            tests[name] = (module_name, 'get_device_info')
        elif hasattr(module, name):
            tests[name] = (module_name, name)

    # Дополнительные тесты вне папки progTest
    if importlib.util.find_spec('test_firmware'):
        tests['test_firmware'] = ('test_firmware', 'run')

    return tests


TEST_MAP = _discover_tests()


def list_tests() -> List[str]:
    """Return discovered test names."""
    return sorted(TEST_MAP.keys())


def run_selected_tests(selected: List[str]) -> str:
    start_syslog_server()
    try:
        devices = regression.load_device_configs('config.txt')
        if not devices:
            return 'Нет устройств в config.txt'

        devices, warnings = filter_reachable_devices(devices)
        if not devices:
            warnings.append("\u26a0\ufe0f \"Не удалось подключиться ни к одному домофону. Тестирование отменено.\"")
            return "\n".join(warnings)

        lines: List[str] = list(warnings)
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            for cfg in devices:
                ip = cfg.get('IP_CAMERA', '')
                login = cfg.get('LOGIN', '')
                password = cfg.get('PASSWORD', '')
                lines.append(' '.join(f'{k}={v}' for k, v in cfg.items()))
                for name in selected:
                    mod_info = TEST_MAP.get(name)
                    if not mod_info:
                        lines.append(f'{name}: неизвестный тест')
                        continue
                    module = importlib.import_module(mod_info[0])
                    func = getattr(module, mod_info[1])
                    try:
                        result = func(ip, login, password)
                    except Exception as e:
                        result = f'Ошибка: {e}'
                    lines.append(f'{name}: {result}')
                lines.append('')

        captured = buf.getvalue()

        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'selected_{timestamp}.txt')
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(captured)
            f.write('\n')
            f.write('\n'.join(lines).strip())

        output = (captured + '\n' + '\n'.join(lines)).strip()

        clean = []
        for ln in output.splitlines():
            if 'GET /' in ln or 'POST /' in ln:
                continue
            clean.append(ln)
        return '\n'.join(clean)
    finally:
        stop_syslog_server()

