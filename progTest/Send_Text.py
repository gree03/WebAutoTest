
import requests
from requests.auth import HTTPBasicAuth

def run(ip, login, password, SendText = "Тест", duration = 2):
    url = "http://"+ ip +"/api/v1/display/message"
    auth = HTTPBasicAuth(login, password)
    payload = {"text": SendText,"duration": int(duration)}
    print("Сообщение отправленно")
    try:
        response = requests.post(url, json=payload, auth=auth, timeout=5)
        response.raise_for_status()
        return 'Успешно отправленно'
    except requests.exceptions.RequestException as e:
        return "Ошибка"