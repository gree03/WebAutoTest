# start2.py
import os
import time
import multiprocessing
from datetime import datetime
from progTest.screenshot import run as screenshot_run
from progTest.ParsProshivka import get_device_info as version_run
from ping_utils import filter_reachable_devices
from progTest.Send_Text import run as SeendText
from progTest.initial_launch import run as initalLaunch
from progTest.ResetSeting import run as ResetSeting
# import progTest.my_task  # пример для расширения обработчиков


def load_device_configs(path='config.txt'):
    """
    Считывает config.txt и возвращает список словарей с параметрами.
    Блоки разделяются строками из '_'.
    """
    devices = []
    current = {}
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if line.startswith('_'):
                if current:
                    devices.append(current)
                    current = {}
                continue
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                current[key.strip()] = val.strip()
        if current:
            devices.append(current)
    return devices


def handle_one(cfg):
    """
    Обрабатывает один блок конфигурации и возвращает результат.
    Возвращает словарь:
      - 'Info': данные прошивки
      - 'screenshot': True/False
      - 'Время выполнения (сек)': длительность работы
      - 'Текущее время': метка окончания обработки
    """
    ip = cfg.get('IP_CAMERA')
    login = cfg.get('LOGIN')
    password = cfg.get('PASSWORD')
    MAX_SCREENSHOTS = cfg.get('MAX_SCREENSHOTS')
    reset = cfg.get('RESET')
    
    start_ts = time.time()
    initalLaunch_start = initalLaunch(ip, login, password)
    SeendText_start = SeendText(ip, login, password, "Автотест запущен!", 0)
    screenshot_result = screenshot_run(ip, login, password, int(MAX_SCREENSHOTS))
    version_result = version_run(ip, login, password)
    elapsed = round(time.time() - start_ts, 2)
    SeendText_stop = SeendText(ip, login, password, "Автотест завершён.", 30)
    ResetSeting_resultate = ResetSeting(ip, login, password, int(reset))
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        'Применение конфигурациия': initalLaunch_start,
        'Сообщение': SeendText_start,
        'Info': version_result,
        'screenshot': screenshot_result,
        'Время выполнения (сек)': elapsed,
        'Сброс': ResetSeting_resultate,
        'Текущее время': current_time,
        'Сообщение': SeendText_stop,
        
    }


def run():
    """
    Параллельно обрабатывает все устройства из config.txt и возвращает
    лог в виде строки. Сохраняет файл под именем Regression_<timestamp>.txt
    """
    devices = load_device_configs()
    if not devices:
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

    # Сохраняем лог в папку logs
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"Regression_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, 'w', encoding='utf-8') as log_file:
        log_file.write(log_text)

    return log_text


if __name__ == '__main__':
    print(run())

