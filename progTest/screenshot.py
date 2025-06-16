# screenshot.py
import requests
import time
import os
from datetime import datetime
from PIL import Image
from io import BytesIO

def run(ip, username, password, max_attempts=10000, progress_callback=None):
    """
    Выполняет до max_attempts HTTP GET-запросов к http://{ip}/image.jpg и проверяет, является ли ответ действительным изображением.
    Сохраняет успешные скриншоты в logs/screenshots/.
    Выводит промежуточный прогресс в консоль.
    Возвращает словарь:
      - 'success': True (если успех ≥90%), False (иначе)
      - 'success_rate': процент успешных запросов
      - 'attempts': количество попыток
      - 'successes': количество успешных запросов
      - 'error_message': описание последней ошибки (если есть)
    """
    print(f"[{datetime.now()}] Начало теста скриншотов для IP {ip} (max_attempts={max_attempts})")
    url = f"http://{ip}/image.jpg"
    successes = 0
    error_threshold = 100
    consecutive_errors = 0
    last_error = ""

    screenshot_dir = os.path.join("logs", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    for i in range(max_attempts):
        try:
            response = requests.get(url, auth=(username, password), timeout=5)
            if response.status_code != 200:
                consecutive_errors += 1
                last_error = f"Статус ответа: {response.status_code}"
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                consecutive_errors += 1
                last_error = f"Неверный Content-Type: {content_type}"
                continue

            content_length = len(response.content)
            if content_length < 1024:
                consecutive_errors += 1
                last_error = f"Слишком маленький ответ: {content_length} байт"
                continue

            try:
                img = Image.open(BytesIO(response.content))
                img.verify()
            except Exception as e:
                consecutive_errors += 1
                last_error = f"Невалидное изображение: {str(e)}"
                continue

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            screenshot_path = os.path.join(screenshot_dir, f"screenshot_{ip.replace(':', '_')}_{timestamp}.jpg")
            with open(screenshot_path, 'wb') as f:
                f.write(response.content)

            successes += 1
            consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            last_error = f"Ошибка: {str(e)}"

        # Выводим прогресс каждые 100 попыток
        if (i + 1) % 100 == 0:
            progress = round(((i + 1) / max_attempts) * 100, 1)
            print(f"[{datetime.now()}] IP {ip}: Выполнено {i + 1}/{max_attempts} ({progress}%), Успехов: {successes}")

        if consecutive_errors >= error_threshold:
            print(f"[{datetime.now()}] IP {ip}: Прервано из-за {consecutive_errors} последовательных ошибок: {last_error}")
            break

        time.sleep(0.01)

    attempts_made = i + 1
    success_rate = round((successes / attempts_made) * 100, 2) if attempts_made > 0 else 0.0
    success = success_rate >= 90.0

    print(f"[{datetime.now()}] Завершение теста для IP {ip}: Попыток: {attempts_made}, Успехов: {successes}, Успех: {success_rate}%")
    return {
        'success': success,
        'success_rate': f"{success_rate}%",
        'attempts': attempts_made,
        'successes': successes,
        'error_message': last_error if not success else ""
    }
