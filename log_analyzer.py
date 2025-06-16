import requests
import os

# Insert your GigaChat API token below
GIGACHAT_TOKEN = ''  # TODO: put your token here

API_URL = 'https://gigachat.devices.sber.ru/api/v1/chat/completions'


def analyze_text(text: str) -> str:
    if not GIGACHAT_TOKEN:
        raise RuntimeError('GigaChat token not configured')
    payload = {
        'model': 'GigaChat',
        'messages': [
            {'role': 'user', 'content': text + '\nПроанализируй результат тестов и дай краткий вывод на русском'}
        ]
    }
    headers = {
        'Authorization': f'Bearer {GIGACHAT_TOKEN}',
        'Content-Type': 'application/json'
    }
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get('choices', [{}])[0].get('message', {}).get('content', '')


def analyze_file(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return analyze_text(content)
