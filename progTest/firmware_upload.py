# firmware_upload.py
import requests
import os
from datetime import datetime

def upload_firmware(ip, username, password, firmware_path):
    """
    Загружает файл прошивки на устройство через upgrader.cgi.

    Args:
        ip: IP-адрес камеры (с портом, если нужно).
        username: Имя пользователя для аутентификации.
        password: Пароль для аутентификации.
        firmware_path: Путь к файлу прошивки (rootfs.squashfs.gk7205v200.signed).

    Returns:
        dict: Результат загрузки:
              - 'success': True/False (успешна ли загрузка).
              - 'error_message': Сообщение об ошибке (если есть).
    """
    url = f"http://{ip}/cgi-bin/upgrader.cgi"
    try:
        with open(firmware_path, 'rb') as f:
            files = {'rootfs': ('rootfs.squashfs.gk7205v200.signed', f, 'application/octet-stream')}
            response = requests.post(url, auth=(username, password), files=files, timeout=60)
        
        if response.status_code == 200:
            return {'success': True, 'error_message': ''}
        else:
            return {'success': False, 'error_message': f"Код ответа: {response.status_code}"}
    
    except requests.RequestException as e:
        return {'success': False, 'error_message': f"Ошибка запроса: {str(e)}"}
    except FileNotFoundError:
        return {'success': False, 'error_message': f"Файл прошивки не найден: {firmware_path}"}
    except Exception as e:
        return {'success': False, 'error_message': f"Ошибка: {str(e)}"}

def reset_firmware(ip, username, password):
    """
    Отправляет POST-запрос для сброса прошивки на устройстве без проверки ответа.

    Args:
        ip: IP-адрес камеры (с портом, если нужно).
        username: Имя пользователя для аутентификации.
        password: Пароль для аутентификации.

    Returns:
        dict: Всегда возвращает успех, так как ответ не проверяется.
    """
    url = f"http://{ip}/cgi-bin/firmware-reset.cgi"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }
    data = {"action": "reset"}
    
    try:
        requests.post(
            url,
            auth=(username, password),
            headers=headers,
            data=data,
            timeout=60
        )
        return {'success': True, 'error_message': ''}
    except Exception as e:
        # Игнорируем ошибки, так как устройство перезагружается
        return {'success': True, 'error_message': f"Игнорируемая ошибка: {str(e)}"}
