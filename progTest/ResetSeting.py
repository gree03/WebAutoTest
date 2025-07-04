import requests
from requests.auth import HTTPBasicAuth
import time
def run(ip: str, login: str, password: str, reset: int = 0) -> str:
    """
    Если reset == 1, выполняет сброс через resetSystemEx.
    Если reset == 0, возвращает сообщение об отключённом сбросе.
    Иначе — сообщение об ошибочном значении reset.
    """
    if reset == 1:
        return runse(ip, login, password)
    elif reset == 0:
        return "Сброс заводским отключен"
    else:
        return ("Неверное значение параметра RESET: "
                "должно быть 1 (сброс) или 0 (не сбрасывать). "
                "Настройте конфиг")

def runse(ip: str, login: str, password: str) -> str:
    """
    Делает GET‐запрос на resetSystemEx и возвращает строку с результатом.
    """
    url = f"http://{ip}/cgi-bin/magicBox.cgi?action=resetSystemEx"
    auth = HTTPBasicAuth(login, password)

    try:
        response = requests.get(url, auth=auth, timeout=5)
        response.raise_for_status()
        time.sleep(10)
        print("Сброс настроек успешный")
        return "Успешный сброс настроек"
    except requests.exceptions.RequestException as e:
        err = str(e)
        print("Ошибка при сбросе настроек:", err)
        return err
