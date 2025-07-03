# acceptance.py
import os
import time
import multiprocessing
from datetime import datetime
from progTest.screenshot import run as screenshot_run
from progTest.ParsProshivka import get_device_info as version_run
from ping_utils import filter_reachable_devices

def load_device_configs(path='config.txt'):
    """
    Считывает config.txt и возвращает список словарей с параметрами.
    Блоки разделяются строками, состоящими хотя бы из '_'.
    """
    devices = []
    current = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if line.startswith('_'):
                    if current:
                        # Устанавливаем MAX_SCREENSHOTS по умолчанию, если не указан
                        if 'MAX_SCREENSHOTS' not in current:
                            current['MAX_SCREENSHOTS'] = '10000'
                        devices.append(current)
                        current = {}
                    continue
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    current[key.strip()] = val.strip()
            if current:
                if 'MAX_SCREENSHOTS' not in current:
                    current['MAX_SCREENSHOTS'] = '10000'
                devices.append(current)
    except FileNotFoundError:
        print(f"[{datetime.now()}] Ошибка: Файл {path} не найден")
    return devices


def handle_one(cfg):
    ip = cfg.get('IP_CAMERA', '')
    login = cfg.get('LOGIN', '')
    password = cfg.get('PASSWORD', '')
    try:
        max_screenshots = int(cfg.get('MAX_SCREENSHOTS', '10000'))
        if max_screenshots <= 0:
            raise ValueError("MAX_SCREENSHOTS должен быть положительным")
    except (ValueError, TypeError) as e:
        max_screenshots = 10000
        print(f"[{datetime.now()}] Ошибка: Неверное значение MAX_SCREENSHOTS для IP {ip} ({str(e)}), используется 10000")

    print(f"[{datetime.now()}] Начало обработки устройства IP {ip} (MAX_SCREENSHOTS={max_screenshots})")
    start_ts = time.time()

    screenshot_result = screenshot_run(ip, login, password, max_attempts=max_screenshots)
    version_result = version_run(ip, login, password)

    elapsed = round(time.time() - start_ts, 2)
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"[{datetime.now()}] Завершение обработки IP {ip}: Время {elapsed} сек, Скриншоты: {screenshot_result['success_rate']}")

    return {
        'Info': version_result,
        'screenshot': screenshot_result['success'],
        'screenshot_success_rate': screenshot_result['success_rate'],
        'screenshot_attempts': screenshot_result['attempts'],
        'screenshot_successes': screenshot_result['successes'],
        'Время выполнения (сек)': elapsed,
        'Текущее время': current_time,
    }


def run():
    print(f"[{datetime.now()}] Запуск теста Acceptance")
    devices = load_device_configs()
    if not devices:
        print(f"[{datetime.now()}] Нет устройств в config.txt")
        return "Нет устройств в config.txt"

    devices, warnings = filter_reachable_devices(devices)
    if not devices:
        warnings.append("\u26a0\ufe0f \"Не удалось подключиться ни к одному домофону. Тестирование отменено.\"")
        return "\n".join(warnings)

    with multiprocessing.Pool(processes=len(devices)) as pool:
        outcomes = pool.map(handle_one, devices)

    lines = list(warnings)
    for cfg, result_dict in zip(devices, outcomes):
        cfg_line = " ".join(f"{k}={v}" for k, v in cfg.items())
        lines.append(cfg_line)
        for name, value in result_dict.items():
            lines.append(f"{name}: {value}")
        lines.append("")

    log_text = "\n".join(lines).strip()

    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"logacceptance_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, 'w', encoding='utf-8') as log_file:
        log_file.write(log_text)

    print(f"[{datetime.now()}] Тест завершен, лог сохранён: {log_path}")
    return log_text


if __name__ == "__main__":
    print(run())

