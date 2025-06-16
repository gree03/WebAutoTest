import os
from datetime import datetime
import importlib
from typing import List
import acceptance

TEST_MAP = {
    'screenshot': ('progTest.screenshot', 'run'),
    'ParsProshivka': ('progTest.ParsProshivka', 'get_device_info'),
    'test_firmware': ('test_firmware', 'run'),
}


def list_tests() -> List[str]:
    return list(TEST_MAP.keys())


def run_selected_tests(selected: List[str]) -> str:
    devices = acceptance.load_device_configs('config.txt')
    if not devices:
        return 'Нет устройств в config.txt'

    lines = []
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
                if name == 'ParsProshivka':
                    result = func(ip, login, password)
                else:
                    result = func(ip, login, password)
            except Exception as e:
                result = f'Ошибка: {e}'
            lines.append(f'{name}: {result}')
        lines.append('')

    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'selected_{timestamp}.txt')
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).strip())
    return '\n'.join(lines).strip()
