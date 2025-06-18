import re
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from bs4 import BeautifulSoup
from typing import Optional

def get_device_info(ip: str, login: str, password: str, use_digest_auth: bool = False) -> str:
    """
    Возвращает многострочную строку с информацией об устройстве в формате:
      Info: MAC: <mac_address>
      Железо:
          Процессор: <value>
          Семейство: <value>
          Сенсор: <value>
          Флэш-память: <value>
          Вариант устройства: <value>
      Прошивка:
          Сборка: <value>
          Majestic: <value>
          Web UI: <value>
          U-Boot: <value>
          UICL: <value>
          MCU: <value>
          Ядро: <value>
          RootFS: <value>
    В случае ошибки возвращает сообщение об ошибке.

    Args:
        ip: IP-адрес устройства (например, '192.168.0.156:85').
        login: Имя пользователя.
        password: Пароль.
        use_digest_auth: Использовать Digest-аутентификацию вместо Basic (по умолчанию False).

    Returns:
        str: Многострочная строка с информацией или сообщением об ошибке.
    """
    session = requests.Session()
    session.auth = HTTPDigestAuth(login, password) if use_digest_auth else HTTPBasicAuth(login, password)

    try:
        # Получаем страницу status.cgi
        r = session.get(f"http://{ip}/cgi-bin/status.cgi", timeout=5)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        # Ключевые слова для поиска
        hardware_keys = ['Процессор', 'Семейство', 'Сенсор', 'Флэш-память', 'Вариант устройства']
        firmware_keys = ['Сборка', 'Majestic', 'Web UI', 'U-Boot', 'UICL', 'MCU', 'Ядро', 'RootFS']
        mac_key = 'MAC'

        # Инициализация результатов
        mac: Optional[str] = None
        hardware: dict = {}
        firmware: dict = {}

        # Поиск MAC-адреса (ожидаем формат XX:XX:XX:XX:XX:XX)
        mac_pattern = re.compile(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}')
        for element in soup.find_all(['dt', 'span', 'div', 'p', 'td']):
            text = element.get_text(strip=True)
            match = mac_pattern.search(text)
            if match:
                mac = match.group(0)
                break
            if mac_key in text and ':' in text:
                potential_mac = text.split(':', 1)[-1].strip()
                if mac_pattern.match(potential_mac):
                    mac = potential_mac
                    break
                sibling = element.find_next_sibling()
                if sibling and mac_pattern.match(sibling.get_text(strip=True)):
                    mac = sibling.get_text(strip=True)
                    break
        if not mac:
            mac = "Не найден"

        # Поиск данных для "Железо" и "Прошивка"
        for dt in soup.find_all('dt'):
            dt_text = dt.get_text(strip=True)
            dd = dt.find_next_sibling('dd')
            if not dd:
                continue
            dd_text = dd.get_text(strip=True)
            # Фильтруем только первое значение до лишнего текста
            clean_value = dd_text.split(',')[0].split('#')[0].strip()
            if dt_text in hardware_keys:
                hardware[dt_text] = clean_value
            elif dt_text in firmware_keys:
                firmware[dt_text] = clean_value

        # Дополнительный поиск по тексту в других элементах
        for element in soup.find_all(['span', 'div', 'p', 'td']):
            text = element.get_text(strip=True)
            for key in hardware_keys + firmware_keys:
                if key in text and ':' in text:
                    clean_value = text.split(':', 1)[-1].split(',')[0].split('#')[0].strip()
                    if key in hardware_keys and key not in hardware:
                        hardware[key] = clean_value
                    elif key in firmware_keys and key not in firmware:
                        firmware[key] = clean_value

        # Получаем Ядро и RootFS из firmware.cgi
        r2 = session.get(f"http://{ip}/cgi-bin/firmware.cgi", timeout=5)
        r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, 'html.parser')

        for dt in soup2.find_all('dt'):
            dt_text = dt.get_text(strip=True)
            dd = dt.find_next_sibling('dd')
            if not dd:
                continue
            dd_text = dd.get_text(strip=True)
            clean_value = dd_text.split(',')[0].split('#')[0].strip()
            if dt_text in ['Ядро', 'RootFS']:
                firmware[dt_text] = clean_value

        # Дополнительный поиск в firmware.cgi
        for element in soup2.find_all(['span', 'div', 'p', 'td']):
            text = element.get_text(strip=True)
            for key in ['Ядро', 'RootFS']:
                if key in text and ':' in text:
                    clean_value = text.split(':', 1)[-1].split(',')[0].split('#')[0].strip()
                    if key not in firmware:
                        firmware[key] = clean_value

        # Формируем вывод в желаемом формате
        lines = [f"Info: MAC: {mac}", "Железо:"]
        for key in hardware_keys:
            lines.append(f"        {key}: {hardware.get(key, '')}")
        lines.append("Прошивка:")
        for key in firmware_keys:
            lines.append(f"        {key}: {firmware.get(key, '')}")

        return "\n".join(lines)

    except requests.exceptions.HTTPError as e:
        if "401" in str(e):
            if not use_digest_auth:
                return get_device_info(ip, login, password, use_digest_auth=True)
            return f"Ошибка аутентификации: {e}"
        return f"Ошибка HTTP: {e}"
    except requests.exceptions.RequestException as e:
        return f"Не удалось подключиться к устройству: {e}"
    except Exception as e:
        return f"Неизвестная ошибка: {e}"


if __name__ == "__main__":
    IP = "192.168.0.156:85"
    LOGIN = "admin"
    PASSWORD = "123456"

    print(get_device_info(IP, LOGIN, PASSWORD))