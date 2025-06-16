# test_firmware.py
import os
import time
import multiprocessing
from datetime import datetime
from typing import List, Dict, Tuple
import requests
from requests.auth import HTTPBasicAuth
from functools import partial
from progTest.firmware_upload import upload_firmware, reset_firmware
from progTest.ParsProshivka import get_device_info

# Константы
ERROR_THRESHOLD = 3
RESET_TIMEOUT = 60
UPLOAD_TIMEOUT = 120
REQUEST_TIMEOUT = 10

def load_firmware_config(config_path: str = 'config.txt') -> Tuple[List[Dict], List[Dict]]:
    """
    Читает config.txt и возвращает список устройств и список прошивок.
    """
    devices = []
    firmware_versions = []
    current = {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('_'):
                    if current:
                        if 'MAX_FIRMWARE_UPLOADS' not in current:
                            current['MAX_FIRMWARE_UPLOADS'] = '10'
                        devices.append(current)
                        current = {}
                    continue
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key, val = key.strip(), val.strip()
                    current[key] = val
                    if key == 'FIRMWARE_VERSIONS' and val:
                        # Парсим FIRMWARE_VERSIONS=версия:путь,версия:путь
                        for item in val.split(','):
                            if ':' in item:
                                version, path = item.split(':', 1)
                                firmware_versions.append({'version': version.strip(), 'path': path.strip()})
        if current:
            if 'MAX_FIRMWARE_UPLOADS' not in current:
                current['MAX_FIRMWARE_UPLOADS'] = '10'
            devices.append(current)
    except FileNotFoundError:
        log_progress(f"Ошибка: Файл {config_path} не найден")
    if not firmware_versions:
        log_progress("Ошибка: FIRMWARE_VERSIONS не указаны в config.txt")
    return devices, firmware_versions

def get_rootfs_version(ip: str, login: str, password: str) -> str:
    """
    Выполняет GET-запрос для получения версии RootFS.
    Возвращает версию (например, '2.5.03.21') или сообщение об ошибке.
    """
    try:
        url = f"http://{ip}/cgi-bin/magicBox.cgi?action=getSoftwareVersion"
        response = requests.get(url, auth=HTTPBasicAuth(login, password), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        # Парсим ответ, например: "version=2.5.03.21\nkernel=2023060714"
        for line in response.text.splitlines():
            if line.startswith("version="):
                return line.split("version=")[1].strip()
        return "Ошибка: Версия RootFS не найдена в ответе"
    except requests.RequestException as e:
        return f"Не удалось подключиться: {str(e)}"
    except Exception as e:
        return f"Неизвестная ошибка: {str(e)}"

def select_next_firmware(current_version: str, firmware_versions: List[Dict]) -> Dict:
    """
    Выбирает следующую прошивку поочерёдно для теста стабильности.
    Если текущая версия неизвестна, возвращает первую прошивку.
    """
    if not firmware_versions:
        raise ValueError("Список прошивок пуст")
    known_versions = [fw['version'] for fw in firmware_versions]
    if current_version not in known_versions:
        log_progress(f"Неизвестная версия RootFS: {current_version}, выбираем {firmware_versions[0]['version']}")
        return firmware_versions[0]
    current_idx = known_versions.index(current_version)
    next_idx = (current_idx + 1) % len(firmware_versions)
    return firmware_versions[next_idx]

def reset_and_wait(ip: str, login: str, password: str, timeout: int) -> None:
    """
    Сбрасывает прошивку и ждёт указанное время.
    """
    log_progress(f"Сброс прошивки на IP {ip}")
    reset_firmware(ip, login, password)
    log_progress(f"Запрос сброса отправлен, ждём {timeout} секунд")
    time.sleep(timeout)

def upload_and_wait(ip: str, login: str, password: str, firmware_path: str, timeout: int) -> Dict:
    """
    Загружает прошивку и ждёт указанное время.
    Возвращает результат загрузки.
    """
    log_progress(f"Загрузка прошивки на IP {ip}: {firmware_path}")
    result = upload_firmware(ip, login, password, firmware_path)
    if result['success']:
        log_progress(f"Ждём {timeout} секунд для завершения загрузки")
        time.sleep(timeout)
    else:
        log_progress(f"Ошибка загрузки прошивки: {result['error_message']}")
    return result

def log_progress(message: str) -> None:
    """
    Логирует сообщение с временной меткой.
    """
    print(f"[{datetime.now()}] {message}")

def test_device(cfg: Dict, firmware_versions: List[Dict]) -> Dict:
    """
    Тестирует одно устройство: чередует прошивки, проверяет версии.
    """
    ip = cfg.get('IP_CAMERA', '')
    login = cfg.get('LOGIN', '')
    password = cfg.get('PASSWORD', '')
    try:
        max_uploads = int(cfg.get('MAX_FIRMWARE_UPLOADS', '10'))
        if max_uploads <= 0:
            raise ValueError("MAX_FIRMWARE_UPLOADS должен быть положительным")
    except (ValueError, TypeError) as e:
        max_uploads = 10
        log_progress(f"Ошибка: Неверное MAX_FIRMWARE_UPLOADS для IP {ip} ({str(e)}), использую 10")

    log_progress(f"Запуск теста прошивки для IP {ip} (MAX_FIRMWARE_UPLOADS={max_uploads})")
    start_ts = time.time()

    successes = {fw['version']: 0 for fw in firmware_versions}
    failures = {fw['version']: 0 for fw in firmware_versions}
    consecutive_errors = 0
    last_error = ""
    attempts = 0

    base_dir = os.path.dirname(os.path.abspath(__file__))

    while attempts < max_uploads and consecutive_errors < ERROR_THRESHOLD:
        # Шаг 1: Проверка текущей версии
        log_progress(f"Проверка текущей прошивки на IP {ip}")
        version_result = get_rootfs_version(ip, login, password)
        if version_result.startswith("Не удалось") or version_result.startswith("Ошибка"):
            consecutive_errors += 1
            last_error = f"Ошибка проверки версии: {version_result}"
            log_progress(last_error)
            break
        current_version = version_result
        log_progress(f"Текущая RootFS: {current_version}")

        # Шаг 2: Выбор следующей прошивки
        firmware = select_next_firmware(current_version, firmware_versions)
        expected_version = firmware['version']
        firmware_path = os.path.join(base_dir, firmware['path'])
        log_progress(f"Выбрана прошивка: {expected_version}")

        # Шаг 3: Сброс прошивки
        reset_and_wait(ip, login, password, RESET_TIMEOUT)

        # Шаг 4: Загрузка прошивки
        upload_result = upload_and_wait(ip, login, password, firmware_path, UPLOAD_TIMEOUT)
        if not upload_result['success']:
            consecutive_errors += 1
            last_error = upload_result['error_message']
            failures[expected_version] += 1
            log_progress(last_error)
        else:
            # Шаг 5: Проверка версии после загрузки
            log_progress(f"Проверка прошивки на IP {ip}")
            new_version = get_rootfs_version(ip, login, password)
            if new_version.startswith("Не удалось") or new_version.startswith("Ошибка"):
                consecutive_errors += 1
                last_error = f"Ошибка проверки версии: {new_version}"
                failures[expected_version] += 1
                log_progress(last_error)
            elif new_version != expected_version:
                consecutive_errors += 1
                last_error = f"Неверная версия RootFS: ожидалась {expected_version}, получена {new_version}"
                failures[expected_version] += 1
                log_progress(last_error)
            else:
                successes[expected_version] += 1
                consecutive_errors = 0
                log_progress(f"Успешное обновление прошивки: RootFS={new_version}")

        # Шаг 6: Сброс после попытки (успех или неудача)
        reset_and_wait(ip, login, password, RESET_TIMEOUT)
        attempts += 1
        if attempts % 2 == 0:
            log_progress(f"IP {ip}: Завершено {attempts}/{max_uploads} попыток, Успехи: {successes}, Неудачи: {failures}")

    elapsed = round(time.time() - start_ts, 2)
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_progress(f"Тест завершён для IP {ip}: Время {elapsed} сек, Успехи: {successes}, Неудачи: {failures}")

    return {
        'Info': get_device_info(ip, login, password),
        'firmware_successes': successes,
        'firmware_failures': failures,
        'firmware_attempts': attempts,
        'Время выполнения (сек)': elapsed,
        'Текущее время': current_time,
        'error_message': last_error if last_error else ""
    }

def test_device_wrapper(cfg: Dict, firmware_versions: List[Dict]) -> Dict:
    """
    Обёртка для test_device, чтобы передать firmware_versions в multiprocessing.
    """
    return test_device(cfg, firmware_versions)

def run():
    """
    Запускает тест прошивки для всех устройств.
    """
    log_progress("Запуск теста загрузки прошивки")
    devices, firmware_versions = load_firmware_config()
    if not devices:
        log_progress("Нет устройств в config.txt")
        return "Нет устройств в config.txt"
    if not firmware_versions:
        log_progress("Нет прошивок в config.txt")
        return "Нет прошивок в config.txt"

    with multiprocessing.Pool(processes=len(devices)) as pool:
        results = pool.map(partial(test_device_wrapper, firmware_versions=firmware_versions), devices)

    lines = []
    for cfg, result_dict in zip(devices, results):
        cfg_line = " ".join(f"{k}={v}" for k, v in cfg.items())
        lines.append(cfg_line)
        for name, value in result_dict.items():
            lines.append(f"{name}: {value}")
        lines.append("")

    log_text = "\n".join(lines).strip()
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"logfirmware_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, 'w', encoding='utf-8') as log_file:
        log_file.write(log_text)

    log_progress(f"Тест завершён, лог сохранён: {log_path}")
    return log_text

if __name__ == "__main__":
    print(run())
