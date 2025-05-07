import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup

def get_device_info(ip: str, login: str, password: str) -> str:
    """
    Возвращает многострочную строку:
      MAC: …
      Железо:
          Процессор: …
          Семейство: …
          Сенсор: …
          Флэш-память: …
          Вариант устройства: …
      Прошивка:
          Сборка: …
          Majestic: …
          Web UI: …
          U-Boot: …
          UICL: …
          MCU: …
          Ядро: …
          RootFS: …
    В случае ошибки возвращает сообщение об ошибке.
    """
    session = requests.Session()
    session.auth = HTTPBasicAuth(login, password)

    try:
        # Получаем и парсим status.cgi
        r = session.get(f"http://{ip}/cgi-bin/status.cgi", timeout=5)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        # Извлекаем MAC
        div_info = soup.find('div', class_='col-md-7 mb-2')
        if not div_info:
            raise RuntimeError("не найден div.col-md-7.mb-2 на status.cgi")
        tokens = [t.strip() for t in div_info.get_text(strip=True).split(',')]
        mac = tokens[-1]

        # Ищем секцию «Информация»
        info_header = soup.find('h2', string='Информация')
        if not info_header:
            raise RuntimeError("не найден заголовок h2 Информация")
        row = info_header.find_next_sibling(
            'div',
            class_='row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4 mb-4'
        )
        if not row:
            raise RuntimeError("не найден блок с классом row… под h2 Информация")

        # Собираем разделы «Железо» и «Прошивка»
        sections = {}
        for col in row.find_all('div', class_='col', limit=2):
            title = col.find('h3')
            dl = col.find('dl', class_='small list')
            if not title or not dl:
                continue
            name = title.get_text(strip=True)
            items = {
                dt.get_text(strip=True): dd.get_text(strip=True)
                for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd'))
            }
            sections[name] = items

        hw = sections.get('Железо', {})
        fw = sections.get('Прошивка', {})

        # Получаем kernel и rootfs из firmware.cgi
        r2 = session.get(f"http://{ip}/cgi-bin/firmware.cgi", timeout=5)
        r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        row2 = soup2.find('div', class_='row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4 mb-4')
        kernel = rootfs = None
        if row2:
            col2 = row2.find('div', class_='col')
            if col2:
                dl2 = col2.find('dl', class_='list small')
                if dl2:
                    items2 = {
                        dt.get_text(strip=True): dd.get_text(strip=True)
                        for dt, dd in zip(dl2.find_all('dt'), dl2.find_all('dd'))
                    }
                    kernel = items2.get('Ядро')
                    rootfs = items2.get('RootFS')

        # Формируем вывод
        lines = [f"MAC: {mac}", "Железо:"]
        for key in ('Процессор', 'Семейство', 'Сенсор', 'Флэш-память', 'Вариант устройства'):
            if key in hw:
                lines.append(f"        {key}: {hw[key]}")

        lines.append("Прошивка:")
        for key in ('Сборка', 'Majestic', 'Web UI', 'U-Boot', 'UICL', 'MCU'):
            if key in fw:
                lines.append(f"        {key}: {fw[key]}")
        # Добавляем ядро и rootfs
        lines.append(f"        Ядро: {kernel}")
        lines.append(f"        RootFS: {rootfs}")

        return "\n".join(lines)

    except requests.exceptions.RequestException as e:
        return f"Не удалось подключиться к устройству: {e}"
    except requests.exceptions.HTTPError as e:
        return f"Ошибка HTTP: {e}"
    except RuntimeError as e:
        return f"Ошибка парсинга: {e}"
    except Exception as e:
        return f"Неизвестная ошибка: {e}"


if __name__ == "__main__":
    IP       = "192.168.0.245:85"
    LOGIN    = "admin"
    PASSWORD = "123456"

    print(get_status_info(IP, LOGIN, PASSWORD))
