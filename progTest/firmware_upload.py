import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from datetime import datetime
import os

def upload_firmware(ip, username, password, firmware_path, use_digest_auth: bool = False):
    """
    Загружает файл прошивки на устройство через upgrader.cgi.

    Args:
        ip: IP-адрес камеры (с портом, если нужно).
        username: Имя пользователя для аутентификации.
        password: Пароль для аутентификации.
        firmware_path: Путь к файлу прошивки (rootfs.squashfs.gk7205v200.signed).
        use_digest_auth: Использовать Digest-аутентификацию вместо Basic (по умолчанию False).

    Returns:
        dict: Результат загрузки:
              - 'success': True/False (успешна ли загрузка).
              - 'error_message': Сообщение об ошибке (если есть).
    """
    url = f"http://{ip}/cgi-bin/upgrader.cgi"
    auth = HTTPDigestAuth(username, password) if use_digest_auth else HTTPBasicAuth(username, password)
    try:
        with open(firmware_path, 'rb') as f:
            files = {'rootfs': ('rootfs.squashfs.gk7205v200.signed', f, 'application/octet-stream')}
            response = requests.post(url, auth=auth, files=files, timeout=120)
        
        if response.status_code == 200:
            return {'success': True, 'error_message': ''}
        else:
            if response.status_code == 401 and not use_digest_auth:
                return upload_firmware(ip, username, password, firmware_path, use_digest_auth=True)
            return {'success': False, 'error_message': f"Код ответа: {response.status_code}, Текст: {response.text[:200]}"}
    
    except requests.RequestException as e:
        return {'success': False, 'error_message': f"Ошибка запроса: {str(e)}"}
    except FileNotFoundError:
        return {'success': False, 'error_message': f"Файл прошивки не найден: {firmware_path}"}
    except Exception as e:
        return {'success': False, 'error_message': f"Неизвестная ошибка: {str(e)}"}

def reset_firmware(ip, username, password, use_digest_auth: bool = False):
    """
    Отправляет POST-запрос для сброса прошивки на устройстве без проверки ответа.

    Args:
        ip: IP-адрес камеры (с портом, если нужно).
        username: Имя пользователя для аутентификации.
        password: Пароль для аутентификации.
        use_digest_auth: Использовать Digest-аутентификацию вместо Basic (по умолчанию False).

    Returns:
        dict: Результат сброса.
    """
    url = f"http://{ip}/cgi-bin/firmware-reset.cgi"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }
    data = {"action": "reset"}
    auth = HTTPDigestAuth(username, password) if use_digest_auth else HTTPBasicAuth(username, password)
    
    try:
        response = requests.post(
            url,
            auth=auth,
            headers=headers,
            data=data,
            timeout=60
        )
        if response.status_code == 401 and not use_digest_auth:
            return reset_firmware(ip, username, password, use_digest_auth=True)
        return {'success': True, 'error_message': ''}
    except Exception as e:
        return {'success': True, 'error_message': f"Игнорируемая ошибка: {str(e)}"}
