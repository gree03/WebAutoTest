"""
    parse_config_file() — парсит config.txt, извлекая IP, логин и пароль всех камер.

    _run_target(func) — запускает функцию теста (run) и сохраняет результат в глобальную переменную _last_result.

    run_mode() — POST-эндпоинт /run/{mode} запускает regression.run или acceptance.run в отдельном процессе. Если тест уже запущен — возвращает busy.

    stop_run() — останавливает активный процесс, отправляет текст "Принудительное завершение" на каждую камеру через SendText, завершает процесс и возвращает результат.

Назначение: обеспечить безопасный запуск тестов через HTTP и возможность их остановки с уведомлением устройств.
"""
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import multiprocessing
from typing import Optional, Callable
import progTest.Send_Text as SendText
import re
router = APIRouter()

_process: Optional[multiprocessing.Process] = None
_last_result: Optional[str] = None

def parse_config_file(filepath="config.txt"):
    devices = []
    pattern = r"IP_CAMERA=(?P<ip>[\d.]+):\d+\s+login=(?P<login>\S+)\s+password=(?P<password>\S+)"
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(pattern, line.strip())
            if match:
                ip = match.group("ip")
                login = match.group("login")
                password = match.group("password")
                devices.append((ip, login, password))
    return devices

def _run_target(func: Callable[[], str]):
    global _last_result
    try:
        _last_result = func()
    except Exception as exc:
        _last_result = f'Ошибка: {exc}'


@router.post('/run/{mode}')
async def run_mode(mode: str, background_tasks: BackgroundTasks):
    global _process
    if _process and _process.is_alive():
        return JSONResponse({'status': 'busy'})
    if mode == 'regression':
        import Regression as regression
        target = regression.run
    else:
        import acceptance
        target = acceptance.run
    proc = multiprocessing.Process(target=_run_target, args=(target,))
    _process = proc
    proc.start()
    background_tasks.add_task(proc.join)
    return JSONResponse({'status': 'started', 'mode': mode})


async def stop_run():
    devices = parse_config_file()

    # Отправка текста на каждую камеру
    for ip, login, password in devices:
        try:
            SendText(ip, login, password, "Принудительное завершение", 10)
        except Exception as e:
            print(f"[WARNING] Не удалось отправить сообщение на {ip}: {e}")

    global _process
    if _process and _process.is_alive():
        _process.terminate()
        _process.join()
        return {'status': 'stopped', 'result': _last_result}
    return {'status': 'idle'}