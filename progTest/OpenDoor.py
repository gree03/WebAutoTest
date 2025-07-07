#!/usr/bin/env python3
# open_door.py

import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from syslog_server import LogDomofon
import time
import re
import paho.mqtt.publish as publish

def run(ip: str, login: str, password: str, attempt: int = 3):
    host_only = ip.split(':')[0]

    url = f"http://{ip}/api/v1/doors/1/open"
    auth = HTTPBasicAuth(login, password)
    header_ts_pattern = re.compile(r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
    open_pattern = re.compile(r'STAT/DOOR1:\s*1')

    api_success = 0
    mqtt_success = 0
    key_success = 0
    resp = requests.post(url, auth=auth, timeout=5)
    for num in range(1, attempt + 1):
        print("\nОжидание 3 секунды перед API...")
        time.sleep(3)

        start_time = datetime.now().replace(microsecond=0)
        print(f"[Попытка {num}] Этап 1: Отправка API-команды на {url} в {start_time}...")
        try:
            resp = requests.post(url, auth=auth, timeout=5)
        except requests.RequestException as e:
            print(f"[Попытка {num}] Ошибка HTTP-запроса: {e}")
            continue

        if resp.status_code == 204:
            print("Ждём 3 секунды перед проверкой логов...")
            time.sleep(3)

            print(f"[Попытка {num}] Проверяем логи после API-команды...")
            found = False
            deadline = time.time() + 7

            for line in LogDomofon(host_only, follow=True):
                if time.time() > deadline:
                    print(f"[Попытка {num}] Время ожидания лога истекло.")
                    break

                m_header = header_ts_pattern.match(line)
                if not m_header:
                    continue
                try:
                    log_ts = datetime.strptime(m_header.group('ts'), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

                delta = (log_ts - start_time).total_seconds()
                if abs(delta) > 10:
                    continue

                if open_pattern.search(line):
                    print(f"[Попытка {num}] ✅ Дверь открыта по API (лог {log_ts}, дельта {delta:.1f}с).")
                    api_success += 1
                    found = True
                    break

            if not found:
                print(f"[Попытка {num}] ❌ Подтверждающий лог после API не найден.")
        else:
            print(f"[Попытка {num}] Некорректный код ответа: {resp.status_code}")

        print("Ждём 3 секунды перед MQTT этапом...")
        time.sleep(3)

        mqtt_start = datetime.now().replace(microsecond=0)
        print(f"[Попытка {num}] Этап 2: Отправка команды MQTT (ESP/Relay6CH/Door_2: 1)...")
        try:
            publish.single(
                topic="ESP/Relay6CH/Door_2",
                payload="1",
                hostname="m8.wqtt.ru",
                port=19376,
                auth={"username": "u_SV3FSP", "password": "xRFgu00s"},
                keepalive=5,
            )
        except Exception as e:
            print(f"[Попытка {num}] Ошибка при отправке MQTT: {e}")
            continue

        print("Ждём 3 секунды перед проверкой логов MQTT...")
        time.sleep(3)

        print(f"[Попытка {num}] Проверяем логи после MQTT-команды...")
        found_mqtt = False
        deadline = time.time() + 7

        for line in LogDomofon(host_only, follow=True):
            if time.time() > deadline:
                print(f"[Попытка {num}] Время ожидания лога MQTT истекло.")
                break

            m_header = header_ts_pattern.match(line)
            if not m_header:
                continue
            try:
                log_ts = datetime.strptime(m_header.group('ts'), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            delta = (log_ts - mqtt_start).total_seconds()
            if abs(delta) > 10:
                continue

            if open_pattern.search(line):
                print(f"[Попытка {num}] ✅ Дверь открыта по MQTT (лог {log_ts}, дельта {delta:.1f}с).")
                mqtt_success += 1
                found_mqtt = True
                break

        if not found_mqtt:
            print(f"[Попытка {num}] ❌ Подтверждающий лог после MQTT не найден.")

        print("Ждём 3 секунды перед этапом ключа...")
        time.sleep(3)

        key_start = datetime.now().replace(microsecond=0)
        print(f"[Попытка {num}] Этап 3: Отправка команды ключом (ESP/Relay6CH/Servo)...")
        try:
            publish.single(
                topic="ESP/Relay6CH/Servo",
                payload="speed:15 Angle:75",
                hostname="m8.wqtt.ru",
                port=19376,
                auth={"username": "u_SV3FSP", "password": "xRFgu00s"},
                keepalive=5,
            )
        except Exception as e:
            print(f"[Попытка {num}] Ошибка при отправке команды ключом: {e}")
            continue

        print("Ждём 3 секунды перед проверкой логов ключа...")
        time.sleep(3)

        print(f"[Попытка {num}] Проверяем логи после команды ключом...")
        found_key = False
        deadline = time.time() + 7

        for line in LogDomofon(host_only, follow=True):
            if time.time() > deadline:
                print(f"[Попытка {num}] Время ожидания лога ключа истекло.")
                break

            m_header = header_ts_pattern.match(line)
            if not m_header:
                continue
            try:
                log_ts = datetime.strptime(m_header.group('ts'), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            delta = (log_ts - key_start).total_seconds()
            if abs(delta) > 10:
                continue

            if open_pattern.search(line):
                print(f"[Попытка {num}] ✅ Дверь открыта по ключу (лог {log_ts}, дельта {delta:.1f}с).")
                key_success += 1
                found_key = True
                break

        if not found_key:
            print(f"[Попытка {num}] ❌ Подтверждающий лог после ключа не найден.")

        if num < attempt:
            print("Ждём 3 секунд перед следующей полной попыткой...")
            time.sleep(3)

    result = (
        f"\nСтатистика:\n"
        f"API метод: {api_success} из {attempt} попыток\n"
        f"Открытие физической кнопкой: {mqtt_success} из {attempt} попыток\n"
        f"Открытие ключом: {key_success} из {attempt} попыток"
    )
    print(result)
    return result
