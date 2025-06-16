import os
from yandex_cloud_ml_sdk import YCloudML
import re
# Укажи свой IAM-токен или API-ключ и folder_id от Yandex Cloud
YANDEX_API_TOKEN = '№'  # TODO: заменить на твой токен
YANDEX_FOLDER_ID = '№'         # TODO: заменить на свой folder_id


# ⚙️ Инициализация SDK и модели
sdk = YCloudML(folder_id=YANDEX_FOLDER_ID, auth=YANDEX_API_TOKEN)
model = sdk.models.completions("yandexgpt-lite", model_version="deprecated").configure(
    temperature=0.3
)

# 📄 Функция разбивки текста на абзацы
def format_to_paragraphs(text: str, max_sentences_per_paragraph=2) -> str:
    sentences = re.split(r'(?<=[.!?…])\s+', text.strip())
    paragraphs = [
        ' '.join(sentences[i:i + max_sentences_per_paragraph])
        for i in range(0, len(sentences), max_sentences_per_paragraph)
    ]
    return '\n\n'.join(paragraphs)


# 🧠 Анализ текста с ИИ
def analyze_text(text: str) -> str:
    try:
        result = model.run(
    [
        {
            "role": "system",
            "text": """Проанализируй результат тестов и дай очень краткий ответ. Пример:
‘Домофон с IP = 192.168.0.77:85: Успешный скриншоты 100% из 100%’.
Если есть какие-то ошибки, сообщи об этом. Пример:
‘Домофон с IP = 192.168.0.74:85: Провальный, не удалось взять скриншоты’."""
        },
        {"role": "user", "text": text}
    ],
    timeout=60
)


        if not result:
            return ""

        raw_output = result[0].text
        return format_to_paragraphs(raw_output)

    except Exception as e:
        print("❌ Ошибка при запросе к Яндекс GPT:", e)
        return "Ошибка анализа"


# 📁 Анализ содержимого файла
def analyze_file(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Файл не найден: {path}")
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return analyze_text(content)

