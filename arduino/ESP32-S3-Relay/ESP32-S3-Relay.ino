#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <PubSubClient.h>

// ==================== НАСТРОЙКИ: скорректируйте под своё железо ====================

// 1) Пины для реле (Relay 6CH). Предполагаем, что реле 1 управляется relayPin1, реле 2 — relayPin2.
//    Логика: digitalWrite(pin, LOW) = включено; digitalWrite(pin, HIGH) = выключено.
const int relayPin1 = 1;   // <-- ЗДЕСЬ НАСТРОИТЬ: конкретный GPIO для реле 1
const int relayPin2 = 2;   // <-- ЗДЕСЬ НАСТРОИТЬ: конкретный GPIO для реле 2
// Если хотите управлять всеми 6 реле, добавьте остальные пины в массив и расширьте логику по аналогии.

// 2) ADC-пины для делителей напряжения (канал Door 1 и Door 2).
//    ESP32 ADC1: например GPIO34 = ADC1_CHANNEL_6, GPIO35 = ADC1_CHANNEL_7.
//    Скорректируйте, если используются другие пины.
const int adcPin1 = 34;  // канал Door 1
const int adcPin2 = 35;  // канал Door 2

// 3) Значения резисторов делителя для каждого канала. Меняйте под вашу схему.
//    Пример: R1 = 100k, R2 = 33k → коэффициент ≈ 0.248 (12В → ~2.98В).
const float R1_chan1 = 100000.0; // Ом, верхний резистор для канала 1
const float R2_chan1 = 33000.0;  // Ом, нижний резистор для канала 1
const float R1_chan2 = 100000.0; // Ом, верхний резистор для канала 2
const float R2_chan2 = 33000.0;  // Ом, нижний резистор для канала 2

// 4) Пины для RGB LED. Предполагаем общий катод, логика HIGH = включить цвет, LOW = выкл.
//    Скорректируйте под вашу схему (обычно 3 GPIO: R, G, B).
const int pinLED_R = 16;  // <-- ЗДЕСЬ НАСТРОИТЬ: GPIO красного канала
const int pinLED_G = 17;  // <-- ЗДЕСЬ НАСТРОИТЬ: GPIO зелёного канала
const int pinLED_B = 18;  // <-- ЗДЕСЬ НАСТРОИТЬ: GPIO синего канала

// 5) Wi-Fi: дефолтные значения, которые применяются, если нет сохранённых в Preferences.
//    Вы можете прописать здесь свои локальные точки доступа, чтобы после первой загрузки
//    устройство автоматически пыталось подключиться.
const char* default_ssid = "DIR-825-ORiA";         // <-- По умолчанию SSID Wi-Fi
const char* default_password = "Domobox485";     // <-- По умолчанию пароль Wi-Fi

// 6) Настройки MQTT по умолчанию (если нет сохранённых):
const char* default_mqtt_server = "192.168.1.100"; // <-- IP или доменное имя брокера
const uint16_t default_mqtt_port = 1883;           // <-- порт MQTT
const char* default_mqtt_user = "";                // <-- если нет аутентификации, оставьте ""
const char* default_mqtt_pass = "";                // <-- если нет аутентификации, оставьте ""

// 7) Таймаут попытки подключения к Wi-Fi (в миллисекундах). Если за это время не подключились — запускаем AP.
const unsigned long WIFI_CONNECT_TIMEOUT = 20000; // 20 секунд

// 8) Настройки AP (точка доступа) для конфигурации:
const char* ap_ssid = "ESP32_Config";       // SSID точки доступа для настройки
const char* ap_password = "config1234";     // Пароль точки доступа (если хотите без пароля, оставьте NULL или "")
// =================================================================================================

// Глобальные объекты и переменные
Preferences preferences;       // для хранения настроек в NVS
WebServer server(80);          // веб-сервер
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Переменные для хранения настроек (будут загружаться из Preferences или дефолтные):
String wifiSSID;
String wifiPassword;
String mqttServerAddr;
uint16_t mqttPort;
String mqttUser;
String mqttPass;

// Флаги состояния подключения:
bool wifiConnected = false;
bool mqttConnected = false;

// Неблокирующие переменные для управления реле:
bool door1Active = false;
unsigned long door1StartTime = 0;
bool door2Active = false;
unsigned long door2StartTime = 0;
const unsigned long relayOnDuration = 2000; // 2 секунды

// Публикация статуса напряжения:
unsigned long lastPublishTime1 = 0;
unsigned long lastPublishTime2 = 0;
const unsigned long publishInterval = 1000; // 1 секунда

// ======== ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ RGB LED ========
// Устанавливает состояние RGB-светодиода:
// red, green, blue — true = включить соответствующий цвет, false = выключить.
void setLEDColor(bool red, bool green, bool blue) {
  digitalWrite(pinLED_R, red ? HIGH : LOW);
  digitalWrite(pinLED_G, green ? HIGH : LOW);
  digitalWrite(pinLED_B, blue ? HIGH : LOW);
}

// Вызывается при изменении статусов Wi-Fi/MQTT, чтобы обновить цвет LED:
// - Нет Wi-Fi: красный
// - Есть Wi-Fi, нет MQTT: синий
// - Есть Wi-Fi и MQTT: зелёный
void updateLEDState() {
  if (!wifiConnected) {
    // Нет Wi-Fi: красный
    setLEDColor(true, false, false);
  } else {
    if (mqttConnected) {
      // Wi-Fi + MQTT: зелёный
      setLEDColor(false, true, false);
    } else {
      // Wi-Fi, но нет MQTT: синий
      setLEDColor(false, false, true);
    }
  }
}

// ======== ФУНКЦИИ ДЛЯ ЧТЕНИЯ НАПРЯЖЕНИЯ ЧЕРЕЗ ДЕЛИТЕЛЬ ========
// Усреднённое чтение ADC и преобразование в Vin по делителю.
// channel = 1 или 2.
float readVin(int channel) {
  int pin;
  float R1, R2;
  if (channel == 1) {
    pin = adcPin1;
    R1 = R1_chan1;
    R2 = R2_chan1;
  } else {
    pin = adcPin2;
    R1 = R1_chan2;
    R2 = R2_chan2;
  }
  // Фиктивное чтение для переключения канала (ESP32 ADC мультиплексор)
  analogRead(pin);
  delayMicroseconds(50); // короткая пауза для установления входного напряжения

  // Усреднение нескольких измерений для сглаживания:
  const int N = 10;
  long sum = 0;
  for (int i = 0; i < N; i++) {
    sum += analogRead(pin);
    delay(5);
  }
  float rawAvg = sum / (float)N; // среднее значение 0..4095
  // Преобразуем в напряжение на входе ADC. Допускаем Vref≈3.3В.
  float Vadc = rawAvg / 4095.0 * 3.3;
  // Вычисляем исходное Vin по делителю:
  float Vin = Vadc * (R1 + R2) / R2;
  return Vin;
}

// ======== ФУНКЦИИ ДЛЯ MQTT ========
// Callback при получении сообщений
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Преобразуем payload в строку:
  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }
  Serial.printf("[MQTT] Получено сообщение. Топик: %s, Payload: %s\n", topic, msg.c_str());

  // Обрабатываем команды открытия двери:
  // Топики: "ESP/Relay6CH/Open_1_Door" и "ESP/Relay6CH/Open_2_Door"
  if (String(topic) == "ESP/Relay6CH/Open_1_Door") {
    if (msg == "1") {
      // Включаем реле 1 на 2 секунды
      if (!door1Active) {
        Serial.println("Активируем Door1: включаем реле 1");
        digitalWrite(relayPin1, LOW); // включить (LOW = ON)
        door1Active = true;
        door1StartTime = millis();
      }
    }
    // Можно обрабатывать другие payload (например "0" для немедленного отключения), но по задаче только "1".
  }
  else if (String(topic) == "ESP/Relay6CH/Open_2_Door") {
    if (msg == "1") {
      if (!door2Active) {
        Serial.println("Активируем Door2: включаем реле 2");
        digitalWrite(relayPin2, LOW); // включить (LOW = ON)
        door2Active = true;
        door2StartTime = millis();
      }
    }
  }
  // Если нужны другие топики, добавляйте здесь.
}

// Пытаемся подключиться к MQTT-брокеру.
// Возвращаем true, если подключились, иначе false.
bool connectToMQTT() {
  if (mqttClient.connected()) {
    return true;
  }
  Serial.printf("[MQTT] Попытка подключения к брокеру %s:%u ...\n", mqttServerAddr.c_str(), mqttPort);
  // При желании можно использовать client ID с уникальной частью, например MAC:
  String clientId = "ESP32Relay6CH-";
  clientId += String((uint32_t)ESP.getEfuseMac(), HEX);
  bool ok;
  if (mqttUser.length() > 0) {
    ok = mqttClient.connect(clientId.c_str(), mqttUser.c_str(), mqttPass.c_str());
  } else {
    ok = mqttClient.connect(clientId.c_str());
  }
  if (ok) {
    Serial.println("[MQTT] Подключено к брокеру");
    // Подписываемся на нужные топики:
    mqttClient.subscribe("ESP/Relay6CH/Open_1_Door");
    mqttClient.subscribe("ESP/Relay6CH/Open_2_Door");
    // После подписки обновляем флаг:
    mqttConnected = true;
    updateLEDState();
    // Можно сразу публиковать исходное состояние напряжения:
    float vin1 = readVin(1);
    float vin2 = readVin(2);
    char buf[50];
    snprintf(buf, sizeof(buf), "%.2f", vin1);
    mqttClient.publish("ESP/Relay6CH/Door_1_Stat", buf, true);
    snprintf(buf, sizeof(buf), "%.2f", vin2);
    mqttClient.publish("ESP/Relay6CH/Door_2_Stat", buf, true);
    return true;
  } else {
    Serial.printf("[MQTT] Ошибка подключения, код: %d. Попробуем позже.\n", mqttClient.state());
    mqttConnected = false;
    updateLEDState();
    return false;
  }
}

// ======== ВЕБ-СЕРВЕР: страницы для настройки и диагностики ========
// Форма конфигурации (страница AP-режима и страница STA-режима, если захотим перенастроить).
String generateConfigPage(bool isAP) {
  // isAP = true, когда мы в AP-режиме, ждем ввода новых настроек.
  // isAP = false, когда в STA-режиме и Wi-Fi уже есть, хотим показать текущие настройки и дать ссылку на перенастройку.
  String page = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>ESP32 Configuration</title></head><body>";
  page += "<h2>Настройки устройства ESP32</h2>";
  if (isAP) {
    page += "<p>Режим настройки (AP). Введите Wi-Fi и MQTT параметры:</p>";
  } else {
    page += "<p>Режим STA. Текущие сохранённые настройки:</p>";
  }
  page += "<form action=\"/save\" method=\"POST\">";
  page += "Wi-Fi SSID:<br><input type=\"text\" name=\"ssid\" value=\"" + wifiSSID + "\"><br>";
  page += "Wi-Fi Password:<br><input type=\"password\" name=\"password\" value=\"" + wifiPassword + "\"><br>";
  page += "MQTT Server:<br><input type=\"text\" name=\"mqtt_server\" value=\"" + mqttServerAddr + "\"><br>";
  page += "MQTT Port:<br><input type=\"number\" name=\"mqtt_port\" value=\"" + String(mqttPort) + "\"><br>";
  page += "MQTT User:<br><input type=\"text\" name=\"mqtt_user\" value=\"" + mqttUser + "\"><br>";
  page += "MQTT Password:<br><input type=\"password\" name=\"mqtt_pass\" value=\"" + mqttPass + "\"><br><br>";
  page += "<input type=\"submit\" value=\"Сохранить и перезагрузить\">";
  page += "</form>";
  if (!isAP) {
    page += "<p><a href=\"/reconfig\">Перейти в режим перенастройки (AP)</a></p>";
    page += "<p>Текущий Wi-Fi IP: " + WiFi.localIP().toString() + "</p>";
    page += "<p>MQTT: " + String(mqttConnected ? "Подключён" : "Не подключён") + "</p>";
  }
  page += "</body></html>";
  return page;
}

// Обработчик GET "/" для настройки/информации:
void handleRoot() {
  bool isAP = WiFi.getMode() == WIFI_AP && WiFi.softAPgetStationNum() >= 0 && !wifiConnected;
  // Если стартовали в AP-режиме (нет Wi-Fi подключения), isAP=true.
  // Иначе, если STA-mode & Wi-Fi подключён, isAP=false.
  String page = generateConfigPage(isAP);
  server.send(200, "text/html; charset=utf-8", page);
}

// Обработчик POST "/save": сохраняем настройки из формы и перезагружаемся.
void handleSave() {
  // Читаем параметры формы:
  if (server.hasArg("ssid") && server.hasArg("password") &&
      server.hasArg("mqtt_server") && server.hasArg("mqtt_port") &&
      server.hasArg("mqtt_user") && server.hasArg("mqtt_pass")) {
    String newSSID = server.arg("ssid");
    String newPass = server.arg("password");
    String newMqttServer = server.arg("mqtt_server");
    uint16_t newMqttPort = server.arg("mqtt_port").toInt();
    String newMqttUser = server.arg("mqtt_user");
    String newMqttPass = server.arg("mqtt_pass");

    // Сохраняем в Preferences:
    preferences.begin("config", false);
    preferences.putString("wifiSSID", newSSID);
    preferences.putString("wifiPassword", newPass);
    preferences.putString("mqttServer", newMqttServer);
    preferences.putUInt("mqttPort", newMqttPort);
    preferences.putString("mqttUser", newMqttUser);
    preferences.putString("mqttPass", newMqttPass);
    preferences.end();

    // Отправляем ответ и перезагружаемся:
    server.send(200, "text/html; charset=utf-8",
                "<html><body><h3>Настройки сохранены. Перезагрузка...</h3></body></html>");
    delay(2000);
    ESP.restart();
  } else {
    server.send(400, "text/plain", "Недостаточно параметров");
  }
}

// Обработчик "/reconfig": сброс соединения Wi-Fi и переход в AP-режим
void handleReconfig() {
  server.send(200, "text/html; charset=utf-8",
              "<html><body><h3>Переключение в режим настройки (AP)...</h3></body></html>");
  delay(1000);
  // Отключаем STA-mode и запускаем AP:
  WiFi.disconnect(true);
  delay(1000);
  // Запуск AP:
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ap_ssid, ap_password);
  Serial.println("Запущен AP для перенастройки");
  // RGB LED: пометим, что сейчас нет Wi-Fi STA, значит будет красный:
  wifiConnected = false;
  updateLEDState();
  // Остальное продолжит выполняться в loop: веб-сервер уже запущен и ждёт запросов.
}

// ======== SETUP ========
void setup() {
  Serial.begin(115200);
  delay(100);

  // Инициализируем пины:
  pinMode(relayPin1, OUTPUT);
  digitalWrite(relayPin1, HIGH); // OFF (предполагая LOW = ON)
  pinMode(relayPin2, OUTPUT);
  digitalWrite(relayPin2, HIGH); // OFF
  pinMode(pinLED_R, OUTPUT);
  pinMode(pinLED_G, OUTPUT);
  pinMode(pinLED_B, OUTPUT);
  // Сразу выставим RGB: нет Wi-Fi → красный.
  wifiConnected = false;
  mqttConnected = false;
  updateLEDState();

  // Инициализация ADC:
  analogReadResolution(12); // 12 бит
  analogSetPinAttenuation(adcPin1, ADC_11db); // диапазон до ~3.3В
  analogSetPinAttenuation(adcPin2, ADC_11db);

  // Загружаем настройки из Preferences:
  preferences.begin("config", true);
  wifiSSID = preferences.getString("wifiSSID", "");
  wifiPassword = preferences.getString("wifiPassword", "");
  mqttServerAddr = preferences.getString("mqttServer", "");
  mqttPort = preferences.getUInt("mqttPort", 0);
  mqttUser = preferences.getString("mqttUser", "");
  mqttPass = preferences.getString("mqttPass", "");
  preferences.end();

  // Если нет сохранённых, используем дефолтные:
  if (wifiSSID.length() == 0) {
    wifiSSID = String(default_ssid);
    wifiPassword = String(default_password);
    Serial.println("Используются дефолтные Wi-Fi настройки");
  } else {
    Serial.println("Загружены сохранённые Wi-Fi настройки");
  }
  if (mqttServerAddr.length() == 0 || mqttPort == 0) {
    mqttServerAddr = String(default_mqtt_server);
    mqttPort = default_mqtt_port;
    mqttUser = String(default_mqtt_user);
    mqttPass = String(default_mqtt_pass);
    Serial.println("Используются дефолтные MQTT настройки");
  } else {
    Serial.println("Загружены сохранённые MQTT настройки");
  }

  // Пытаемся подключиться к Wi-Fi (STA-mode):
  Serial.printf("Подключение к Wi-Fi SSID='%s' ...\n", wifiSSID.c_str());
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSSID.c_str(), wifiPassword.c_str());
  unsigned long startAttemptTime = millis();
  while (millis() - startAttemptTime < WIFI_CONNECT_TIMEOUT) {
    if (WiFi.status() == WL_CONNECTED) {
      wifiConnected = true;
      Serial.printf("Wi-Fi подключён, IP: %s\n", WiFi.localIP().toString().c_str());
      break;
    }
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (!wifiConnected) {
    Serial.println("Не удалось подключиться к Wi-Fi: запускаем AP для настройки");
    // Запуск AP для настройки:
    WiFi.mode(WIFI_AP);
    WiFi.softAP(ap_ssid, ap_password);
    Serial.printf("AP запущен: SSID='%s', пароль='%s'\n", ap_ssid, ap_password);
    // RGB LED: уже стоит красный
  } else {
    // Wi-Fi подключён: web-сервер запустим в STA-режиме
    Serial.println("Запускаем веб-сервер в STA-режиме");
  }

  // Настраиваем веб-сервер: в любом режиме AP или STA, обрабатываем одни и те же маршруты:
  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSave);
  server.on("/reconfig", HTTP_GET, handleReconfig);
  server.begin();
  Serial.println("WebServer запущен, ждем запросов");

  // Настраиваем MQTT:
  mqttClient.setServer(mqttServerAddr.c_str(), mqttPort);
  mqttClient.setCallback(mqttCallback);

  // Если Wi-Fi сразу подключён, пытаемся подключиться к MQTT:
  if (wifiConnected) {
    if (connectToMQTT()) {
      Serial.println("MQTT соединение установлено в setup");
    } else {
      Serial.println("Не удалось подключиться к MQTT в setup, будет повтор в loop");
    }
    updateLEDState();
  }
}

// ======== LOOP ========
void loop() {
  // Всегда обрабатываем веб-сервер (и в AP, и в STA режиме)
  server.handleClient();

  // Если в STA режиме и Wi-Fi подключён:
  if (wifiConnected) {
    // MQTT: если не подключён, пытаемся
    if (!mqttClient.connected()) {
      // Сбрасываем флаг mqttConnected, чтобы updateLEDState показал синий (Wi-Fi есть, MQTT нет)
      mqttConnected = false;
      updateLEDState();
      // Пытаемся переподключиться с некоторым интервалом (например, каждые 5 секунд)
      static unsigned long lastMqttAttempt = 0;
      if (millis() - lastMqttAttempt > 5000) {
        lastMqttAttempt = millis();
        connectToMQTT();
      }
    } else {
      // MQTT подключён
      mqttClient.loop();
    }

    // Обработка неблокирующего управления реле:
    unsigned long now = millis();
    if (door1Active) {
      if (now - door1StartTime >= relayOnDuration) {
        // Выключаем реле 1
        digitalWrite(relayPin1, HIGH); // OFF
        Serial.println("Door1: отключаем реле 1 после 2 секунд");
        door1Active = false;
      }
    }
    if (door2Active) {
      if (now - door2StartTime >= relayOnDuration) {
        digitalWrite(relayPin2, HIGH); // OFF
        Serial.println("Door2: отключаем реле 2 после 2 секунд");
        door2Active = false;
      }
    }

    // Публикация статуса напряжения раз в секунду:
    if (mqttClient.connected()) {
      unsigned long t = millis();
      if (t - lastPublishTime1 >= publishInterval) {
        lastPublishTime1 = t;
        float vin1 = readVin(1);
        char buf1[32];
        snprintf(buf1, sizeof(buf1), "%.2f", vin1);
        mqttClient.publish("ESP/Relay6CH/Door_1_Stat", buf1, true);
        Serial.printf("Published Door_1_Stat: %s V\n", buf1);
      }
      if (t - lastPublishTime2 >= publishInterval) {
        lastPublishTime2 = t;
        float vin2 = readVin(2);
        char buf2[32];
        snprintf(buf2, sizeof(buf2), "%.2f", vin2);
        mqttClient.publish("ESP/Relay6CH/Door_2_Stat", buf2, true);
        Serial.printf("Published Door_2_Stat: %s V\n", buf2);
      }
    }
  } else {
    // Если не подключены к Wi-Fi в STA: можно проверить, не подключились ли (например, по кнопке) или просто ждать настройки.
    // Здесь можно добавить автоповтор попытки соединения, но осторожно, чтобы не блокировать AP.
  }

  // Обновляем LED время от времени (или после событий). 
  // Здесь updateLEDState() вызывается после каждой смены wifiConnected/mqttConnected.
  // Можно при желании делать мерцание или иное поведение.
}
