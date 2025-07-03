from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import multiprocessing
from typing import Optional, Callable

router = APIRouter()

_process: Optional[multiprocessing.Process] = None
_last_result: Optional[str] = None


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


@router.post('/stop')
async def stop_run():
    global _process
    if _process and _process.is_alive():
        _process.terminate()
        _process.join()
        return {'status': 'stopped', 'result': _last_result}
    return {'status': 'idle'}
