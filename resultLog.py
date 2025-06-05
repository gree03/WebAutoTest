# resultLog.py
import os
import glob
import re
from datetime import datetime
import matplotlib.pyplot as plt

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
        text = f.read()
    return latest_file, text

def parse_blocks(text):
    blocks = re.split(r"\n\s*\n", text.strip())
    results = []
    for block in blocks:
        scr = re.search(r"screenshot:\s*(True|False)", block, re.IGNORECASE)
        if not scr:
            continue
        is_success = scr.group(1).lower() == 'true'
        success_rate_match = re.search(r"screenshot_success_rate:\s*([\d.]+)%", block)
        success_rate = success_rate_match.group(1) if success_rate_match else "N/A"
        ip_match = re.search(r"IP_CAMERA=([^\s]+)", block)
        ip = ip_match.group(1) if ip_match else 'Unknown'
        if is_success:
            mac_match = re.search(r"MAC:\s*([0-9A-Fa-f:]+)", block)
            if mac_match:
                results.append({
                    'type': 'success',
                    'value': mac_match.group(1),
                    'success_rate': success_rate
                })
        else:
            results.append({
                'type': 'fail',
                'value': ip,
                'success_rate': success_rate
            })
    return results

def save_text_results(results, out_txt):
    lines = []
    for item in results:
        if item['type'] == 'success':
            lines.append(f"MAC: {item['value']} — Успешно (скриншоты: {item['success_rate']}%)")
        else:
            lines.append(f"IP: {item['value']} — Не удалось подключиться к устройству. Проверьте подключение (скриншоты: {item['success_rate']}%)")
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    return lines

def plot_results(percent, out_img):
    color = 'green' if percent >= 90 else 'red'
    plt.figure(figsize=(4, 1.5))
    plt.barh([''], [percent], color=color)
    plt.xlim(0, 100)
    plt.xlabel('% Пройдено')
    plt.title(f'{percent:.0f}%')
    plt.tight_layout()
    plt.savefig(out_img)
    plt.close()

def run():
    latest_file, text = read_latest_log()
    basename = os.path.basename(latest_file)
    ts_match = re.search(r"_(\d{8}_\d{6})\.txt$", basename)
    timestamp = ts_match.group(1) if ts_match else datetime.now().strftime('%Y%m%d_%H%M%S')
    if basename.lower().startswith('logacceptance'):
        prefix = 'acep'
    else:
        prefix = 'regres'
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, 'logs')
    out_txt = os.path.join(log_dir, f"{prefix}_{timestamp}.txt")
    out_img = os.path.join(log_dir, f"{prefix}_{timestamp}.jpg")
    results = parse_blocks(text)
    lines = save_text_results(results, out_txt)
    total = len(results)
    success_count = sum(1 for r in results if r['type'] == 'success')
    percent = (success_count / total * 100) if total > 0 else 0
    plot_results(percent, out_img)
    return "У нас все ок у вас как"

if __name__ == '__main__':
    print(run())