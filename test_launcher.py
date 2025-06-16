# test_launcher.py
"""Utility functions to run selected tests from the progTest package."""
from typing import List, Dict, Callable
from progTest import screenshot, ParsProshivka
import acceptance

# Map of available test names to callables expecting (ip, login, password)
AVAILABLE_TESTS: Dict[str, Callable[[str, str, str], object]] = {
    'screenshot': screenshot.run,
    'version': lambda ip, login, password: ParsProshivka.get_device_info(ip, login, password),
}


def run_selected(test_names: List[str], config_path: str = 'config.txt') -> List[Dict]:
    """Run selected tests for each device from the config file.

    Returns list of results for each device.
    """
    devices = acceptance.load_device_configs(config_path)
    results = []
    for cfg in devices:
        device_res = {'device': cfg.get('IP_CAMERA', '')}
        ip = cfg.get('IP_CAMERA', '')
        login = cfg.get('LOGIN', '')
        password = cfg.get('PASSWORD', '')
        for name in test_names:
            func = AVAILABLE_TESTS.get(name)
            if not func:
                continue
            try:
                device_res[name] = func(ip, login, password)
            except Exception as e:
                device_res[name] = f'Error: {e}'
        results.append(device_res)
    return results
