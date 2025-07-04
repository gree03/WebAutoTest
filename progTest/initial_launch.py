#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time

def run(ip: str, login: str, password: str) -> bool:
    """
    Сбрасывает конфигурацию умного домофона и выполняет дополнительные настройки.
    :param ip: IP-адрес устройства (без порта)
    :param login: логин для HTTP-аутентификации
    :param password: пароль для HTTP-аутентификации
    :return: True, если все запросы выполнены успешно (иначе бросает исключение)
    """
    base_url = f"http://{ip}"
    auth = (login, password)

    # 1. Сброс конфигурации
    config_payload = {
        "system": {"loglevel": -1, "update_link": ""},
        "sip": {"domain": "127.0.0.1:5060", "user": "user", "password": "password"},
        "commutator": {"type": "VIZIT", "mode": 1, "ap_min": 1, "ap_max": 36,
                         "ap_shift": 0, "ap_cnt": [0] * 8, "calltime": 120},
        "volume": {"speaker": 8.0, "mic": 8.0, "sys": 90, "analog_speaker": 100, "analog_mic": 100},
        "display": {
            "rotate": False, "text_speed": 15, "text_color": "FFFFFF", "labels": ["", "", ""],
            "localization": {
                "ENTER_APARTMENT": "ENTER APARTMENT",
                "ENTER_PREFIX": "ENTER PREFIX",
                "CALL": "CALL",
                "CALL_GATE": "CALL GATE",
                "CALL_COMPLETE": "CALL COMPLETE",
                "CONNECT": "CONNECT",
                "OPEN": "OPEN",
                "FAIL_NO_CLIENT": "FAIL NO CLIENT",
                "FAIL_NO_APP_AND_FLAT": "FAIL NO APP AND FLAT",
                "FAIL_LONG_SPEAK": "FAIL LONG SPEAK",
                "FAIL_NO_ANSWER": "FAIL NO ANSWER",
                "FAIL_UNKNOWN": "FAIL UNKNOWN",
                "FAIL_BLACK_LIST": "FAIL BLACK LIST",
                "FAIL_LINE_BUSY": "FAIL LINE BUSY",
                "KEY_DUPLICATE_ERROR": "KEY DUPLICATE ERROR",
                "KEY_READ_ERROR": "KEY READ ERROR",
                "KEY_BROKEN_ERROR": "KEY BROKEN ERROR",
                "KEY_UNSUPPORTED_ERROR": "KEY UNSUPPORTED ERROR",
                "ALWAYS_OPEN": "The door is open",
                "SOS_CALL": "SOS calling",
                "SOS_CONNECT": "SOS connected",
                "SOS_CALL_COMPLETE": "SOS call complete",
                "SOS_ERROR": "SOS error",
                "CONS_CALL": "CONS calling",
                "CONS_CONNECT": "CONS connected",
                "CONS_CALL_COMPLETE": "CONS call complete",
                "CONS_ERROR": "CONS error",
                "KALITKA_CALL": "KALITKA calling",
                "KALITKA_CONNECT": "KALITKA connected",
                "KALITKA_CALL_COMPLETE": "KALITKA call complete",
                "KALITKA_ERROR": "KALITKA error",
                "FRSI_CALL": "FRSI calling",
                "FRSI_CONNECT": "FRSI connected",
                "FRSI_CALL_COMPLETE": "FRSI call complete",
                "FRSI_ERROR": "FRSI error",
                "ALARM_TEXT_1": "ALARM 1",
                "ALARM_TEXT_2": "ALARM 2",
                "ALARM_TEXT_3": "ALARM 3"
            }
        },
        "door": {
            "open_time": 3.0, "open_2_time": 3.0, "relay_open": 0, "lock_invert": False,
            "autocollect": "", "unlock": "", "unlock2": "", "alarm_mode": 0,
            "ble_open": False, "ble_password": "", "ble_rssi": -80,
            "skud_id": "", "aes_token": "", "rfid_pass_en": True,
            "rfid_password": "", "dtmf_open_local": ["#", "2"], "dtmf_open_remote": "#"
        },
        "backlight": {"level": 50}
    }
    print("Начало")
    url = f"{base_url}/api/v1/configuration"
    resp = requests.put(url, json=config_payload, auth=auth, timeout=10)
    resp.raise_for_status()

    # Задержка 5 секунд после отправки конфига
    time.sleep(10)

    # 2. Отключаем агент
    requests.get(
        f"{base_url}/cgi-bin/configManager.cgi?action=setConfig&Agent.Enable=false",
        auth=auth, timeout=5
    ).raise_for_status()

    # 3. Отключаем автообновление
    requests.get(
        f"{base_url}/cgi-bin/configManager.cgi?action=setConfig&Autoupdate.Enable=false",
        auth=auth, timeout=5
    ).raise_for_status()

    # 4. Включаем SysLOG на уровень 8
    requests.get(
        f"{base_url}/cgi-bin/configManager.cgi?action=setConfig&Syslog.Level=8",
        auth=auth, timeout=5
    ).raise_for_status()

    # 5. Указываем SysLog сервер
    requests.get(
        f"{base_url}/cgi-bin/configManager.cgi?action=setConfig&Syslog.Address=192.168.0.69:5514",
        auth=auth, timeout=5
    ).raise_for_status()

    return True
