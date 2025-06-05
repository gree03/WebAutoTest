import os
import glob
import re
from datetime import datetime

def get_latest_log(log_dir):
    files = glob.glob(os.path.join(log_dir, '*.txt'))
    if not files:
        raise FileNotFoundError(f"No .txt files found in {log_dir}")
    parsed = []
    for f in files:
        basename = os.path.basename(f)
        match = re.search(r"_(\d{8}_\d{6})\.txt$", basename)
        if match:
            ts = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
            parsed.append((ts, f))
    if not parsed:
        raise ValueError("No files with timestamp pattern found in filenames")
    return max(parsed, key=lambda x: x[0])[1]

def read_latest_log():
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, 'logs')
    latest_file = get_latest_log(log_dir)
    with open(latest_file, 'r', encoding='utf-8') as f:
        return f.read()

def parse_blocks(text):
    # Разбиваем на блоки по пустой строке
    blocks = re.split(r"\n\s*\n", text.strip())
    results = []
    for block in blocks:
        # Определяем статус screenshot
        scr = re.search(r"screenshot:\s*(True|False)", block, re.IGNORECASE)
        if not scr:
            continue
        is_success = scr.group(1).lower() == 'true'
        if is_success:
            # Успех: берем MAC
            mac_match = re.search(r"MAC:\s*([0-9A-Fa-f:]+)", block)
            if mac_match:
                results.append(f"MAC: {mac_match.group(1)} — Успешно")
        else:
            # Ошибка: берем IP_CAMERA и выводим сообщение
            ip_match = re.search(r"IP_CAMERA=([^\s]+)", block)
            ip = ip_match.group(1) if ip_match else 'Unknown'
            results.append(f"IP: {ip} — Не удалось подключиться к устройству. Проверьте подключение и настройки доступа такие как пароль и логин на вкладке конфиг")
    return results

def run():
    text = read_latest_log()
    lines = parse_blocks(text)
    if not lines:
        return "Нет данных для отображения."
    return "\n".join(lines)

if __name__ == '__main__':
    print(run())
