# start.py
import os
import time
import multiprocessing
from datetime import datetime
from progTest.screenshot import run as screenshot_run
import progTest.primer  # оставляем, если потребуется в будущем
from progTest.ParsProshivka import get_device_info as version_run
# import progTest.other_module  # пример для расширения обработчиков


def load_device_configs(path='config.txt'):
    """
    Считывает config.txt и возвращает список словарей с параметрами.
    Блоки разделяются строками, состоящими хотя бы из '_'.
    """
    devices = []
    current = {}
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            # разделитель блока (линия из '_')
            if line.startswith('_'):
                if current:
                    devices.append(current)
                    current = {}
                continue
            # пропускаем пустые и комментированные строки
            if not line or line.startswith('#'):
                continue
            # разбираем KEY=VALUE
            if '=' in line:
                key, val = line.split('=', 1)
                current[key.strip()] = val.strip()
        # последний блок, если остался
        if current:
            devices.append(current)
    return devices


def handle_one(cfg):
    """
    Обрабатывает один блок конфигурации и возвращает результаты.

    Параметры cfg:
      - IP_CAMERA: адрес камеры
      - LOGIN: логин для доступа
      - PASSWORD: пароль для доступа
      - любые другие ключи (например, TIME, retries и т.д.)

    Возвращает словарь со всеми результатами:
      - 'Info': данные прошивки (version_run)
      - 'screenshot': True/False
      - 'Время выполнения (сек)': время работы функции в секундах
      - 'Текущее время': метка времени окончания обработки
    """
    ip = cfg.get('IP_CAMERA')
    login = cfg.get('LOGIN')
    password = cfg.get('PASSWORD')

    # Засекаем начало обработки
    start_ts = time.time()

    # Основные обработчики
    screenshot_result = screenshot_run(ip, login, password)
    version_result = version_run(ip, login, password)

    # Засекаем конец и вычисляем длительность
    elapsed = time.time() - start_ts
    elapsed_rounded = round(elapsed, 2)

    # Текущее время окончания обработки
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return {
        'Info': version_result,
        'screenshot': screenshot_result,
        'Время выполнения (сек)': elapsed_rounded,
        'Текущее время': current_time,
    }


def run():
    """
    Параллельно обрабатывает все устройства из config.txt и возвращает
    строку с результатами:

      IP_CAMERA=... LOGIN=... PASSWORD=...
      Info: ...
      screenshot: True/False
      Время выполнения (сек): ...
      Текущее время: YYYY-MM-DD HH:MM:SS

    Также сохраняет лог в папку logs с именем logacceptance_<timestamp>.txt
    """
    devices = load_device_configs()
    if not devices:
        return "Нет устройств в config.txt"

    # Запуск обработки в пуле процессов
    with multiprocessing.Pool(processes=len(devices)) as pool:
        outcomes = pool.map(handle_one, devices)

    # Формируем текст лога
    lines = []
    for cfg, result_dict in zip(devices, outcomes):
        # Строка с параметрами устройства
        cfg_line = " ".join(f"{k}={v}" for k, v in cfg.items())
        lines.append(cfg_line)
        # Строки с результатами каждого обработчика
        for name, value in result_dict.items():
            lines.append(f"{name}: {value}")
        lines.append("")

    log_text = "\n".join(lines).strip()

    # Сохраняем лог в папку logs
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"logacceptance_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, 'w', encoding='utf-8') as log_file:
        log_file.write(log_text)

    return log_text


if __name__ == '__main__':
    print(run())
