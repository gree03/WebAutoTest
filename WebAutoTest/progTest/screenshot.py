import requests

def run(ip, username, password):
    url = f"http://{ip}/image.jpg"
    try:
        response = requests.get(url, auth=(username, password), timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False