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
RESET_TIMEOUT = 30
UPLOAD_TIMEOUT = 120
REQUEST_TIMEOUT = 10
PING_TIMEOUT = 5
MAX_PING_ATTEMPTS = 10

def extract_versions(info_str: str) -> Dict:
    """Извлекает версии MCU, UICL и RootFS из строки get_device_info."""
    versions = {'MCU': '', 'UICL': '', 'RootFS': ''}
    lines = info_str.split('\n')
    in_firmware = False
    for line in lines:
        line = line.strip()
        if line == 'Прошивка:':
            in_firmware = True
            continue
        if in_firmware and ':' in line:
            key_value = line.split(':', 1)
            if len(key_value) == 2:
                key = key_value[0].strip()
                value = key_value[1].strip()
                if key in versions:
                    versions[key] = value
    return versions

def wait_for_device(ip: str, timeout: int = PING_TIMEOUT, max_attempts: int = MAX_PING_ATTEMPTS) -> bool:
    """Ждет, пока устройство станет доступным."""
    log_progress(f"Ожидание доступности устройства {ip}")
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"http://{ip}/cgi-bin/status.cgi", timeout=timeout)
            if response.status_code in (200, 401):
                log_progress(f"Устройство {ip} доступно")
                return True
        except requests.RequestException:
            pass
        log_progress(f"Попытка {attempt + 1}/{max_attempts}: устройство {ip} недоступно")
        time.sleep(timeout)
    log_progress(f"Устройство {ip} не стало доступным после {max_attempts} попыток")
    return False

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
    wait_for_device(ip)

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
        wait_for_device(ip)
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
    expected_mcu_change = cfg.get('EXPECTED_MCU_CHANGE', 'True').lower() == 'true'
    expected_uicl_change = cfg.get('EXPECTED_UICL_CHANGE', 'True').lower() == 'true'

    log_progress(f"Запуск теста прошивки для IP {ip} (MAX_FIRMWARE_UPLOADS={max_uploads})")
    start_ts = time.time()

    successes = {fw['version']: 0 for fw in firmware_versions}
    failures = {fw['version']: 0 for fw in firmware_versions}
    consecutive_errors = 0
    last_error = ""
    attempts = 0
    results = []

    base_dir = os.path.dirname(os.path.abspath(__file__))

    while attempts < max_uploads and consecutive_errors < ERROR_THRESHOLD:
        # Шаг 1: Получение начальных версий
        log_progress(f"Проверка текущих версий на IP {ip}")
        initial_info = get_device_info(ip, login, password)
        if initial_info.startswith("Ошибка") or initial_info.startswith("Не удалось"):
            consecutive_errors += 1
            last_error = f"Ошибка получения начальных версий: {initial_info}"
            log_progress(last_error)
            break
        initial_versions = extract_versions(initial_info)
        log_progress(f"Начальные версии: MCU={initial_versions['MCU']}, UICL={initial_versions['UICL']}, RootFS={initial_versions['RootFS']}")

        # Шаг 2: Выбор следующей прошивки
        current_version = initial_versions['RootFS'] or get_rootfs_version(ip, login, password)
        if current_version.startswith("Не удалось") or current_version.startswith("Ошибка"):
            consecutive_errors += 1
            last_error = f"Ошибка проверки версии RootFS: {current_version}"
            log_progress(last_error)
            break
        log_progress(f"Текущая RootFS: {current_version}")

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
            results.append({
                'firmware_version': expected_version,
                'initial_versions': initial_versions,
                'final_versions': {},
                'version_changes': {'mcu_changed': False, 'uicl_changed': False, 'rootfs_changed': False},
                'success': False
            })
        else:
            # Шаг 5: Проверка версий после загрузки
            log_progress(f"Проверка версий после прошивки на IP {ip}")
            final_info = get_device_info(ip, login, password)
            if final_info.startswith("Ошибка") or final_info.startswith("Не удалось"):
                consecutive_errors += 1
                last_error = f"Ошибка получения конечных версий: {final_info}"
                failures[expected_version] += 1
                log_progress(last_error)
                results.append({
                    'firmware_version': expected_version,
                    'initial_versions': initial_versions,
                    'final_versions': {},
                    'version_changes': {'mcu_changed': False, 'uicl_changed': False, 'rootfs_changed': False},
                    'success': False
                })
            else:
                final_versions = extract_versions(final_info)
                new_version = final_versions['RootFS'] or get_rootfs_version(ip, login, password)
                version_changes = {
                    'mcu_changed': initial_versions['MCU'] != final_versions['MCU'] and initial_versions['MCU'] and final_versions['MCU'],
                    'uicl_changed': initial_versions['UICL'] != final_versions['UICL'] and initial_versions['UICL'] and final_versions['UICL'],
                    'rootfs_changed': initial_versions['RootFS'] != new_version and initial_versions['RootFS'] and new_version
                }
                # Отладочный вывод
                log_progress(f"version_changes: {version_changes}")
                log_progress(f"Ожидания: MCU={expected_mcu_change}, UICL={expected_uicl_change}")
                
                # Проверка RootFS (всегда должно совпадать с ожидаемой версией)
                rootfs_status = str(new_version).strip() == str(expected_version).strip()
                
                # Проверка MCU
                mcu_status = True  # По умолчанию True, если проверка не требуется
                if expected_mcu_change:
                    mcu_status = version_changes['mcu_changed']  # Должно измениться
                elif initial_versions['MCU'] and final_versions['MCU']:
                    mcu_status = initial_versions['MCU'] == final_versions['MCU']  # Должно остаться тем же
                
                # Проверка UICL
                uicl_status = True  # По умолчанию True, если проверка не требуется
                if expected_uicl_change:
                    uicl_status = version_changes['uicl_changed']  # Должно измениться
                elif initial_versions['UICL'] and final_versions['UICL']:
                    uicl_status = initial_versions['UICL'] == final_versions['UICL']  # Должно остаться тем же

                if rootfs_status and mcu_status and uicl_status:
                    successes[expected_version] += 1
                    consecutive_errors = 0
                    log_progress(f"Успешное обновление прошивки: RootFS={new_version}, MCU={final_versions['MCU']}, UICL={final_versions['UICL']}")
                else:
                    consecutive_errors += 1
                    last_error = (
                        f"Неверные версии: RootFS ожидалось {expected_version}, получено {new_version} "
                        f"(статус={rootfs_status}), "
                        f"MCU изменился={version_changes['mcu_changed']} (ожидание={expected_mcu_change}, статус={mcu_status}), "
                        f"UICL изменился={version_changes['uicl_changed']} (ожидание={expected_uicl_change}, статус={uicl_status})"
                    )
                    failures[expected_version] += 1
                    log_progress(last_error)

                results.append({
                    'firmware_version': expected_version,
                    'initial_versions': initial_versions,
                    'final_versions': final_versions,
                    'version_changes': version_changes,
                    'success': rootfs_status and mcu_status and uicl_status
                })

        # Шаг 6: Сброс после попытки
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
        'firmware_results': results,
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
            if name == 'Info':
                lines.append(value)
            elif name == 'firmware_results':
                for result in value:
                    lines.append(f"Прошивка {result['firmware_version']}:")
                    lines.append("  Начальные версии:")
                    for k, v in result['initial_versions'].items():
                        lines.append(f"    {k}: {v}")
                    lines.append("  Конечные версии:")
                    for k, v in result['final_versions'].items():
                        lines.append(f"    {k}: {v}")
                    lines.append("  Изменения:")
                    for k, v in result['version_changes'].items():
                        lines.append(f"    {k}: {v}")
                    lines.append(f"  Success: {result['success']}")
            else:
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
