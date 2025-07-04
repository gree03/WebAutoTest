// ESP32-S3-Relay-6CH Firmware for Arduino IDE
// Надёжное управление реле, сервоприводом, сбор телеметрии и гибкая настройка через Web и MQTT

#include <WiFi.h>
#include <WebServer.h>
#include <WiFiClient.h>
#include <PubSubClient.h>
#include <WiFiManager.h>        // https://github.com/tzapu/WiFiManager
#include <ArduinoJson.h>        // https://github.com/bblanchon/ArduinoJson
#include <ESP32Servo.h>         // Библиотека Servo для ESP32: https://github.com/jkb-git/ESP32Servo

// ====== Параметры по умолчанию ======
// ====== Параметры по умолчанию ======
const char* wifiSSIDDefault     = "DIR-825-ORiA";
const char* wifiPasswordDefault = "Domobox485";
const char* mqttHostDefault     = "m8.wqtt.ru";
const uint16_t mqttPortDefault  = 19376;
const char* mqttUserDefault     = "u_SV3FSP";
const char* mqttPasswordDefault = "xRFgu00s";
const char* baseTopic           = "ESP/Relay6CH";

// ====== Параметры по умолчанию ======

// Интервалы
unsigned long adcInterval = 10000;
unsigned long lastAdcTs   = 0;

// Пины реле (Waveshare ESP32-S3-Relay-6CH)
const uint8_t relayCount = 6;
uint8_t relayPins[relayCount]         = {1, 2, 41, 42, 45, 46};
unsigned long relayTimers[relayCount] = {0};

// Сервопривод: состояние и параметры
const int servoPin        = 9;
int currentAngle          = 90;
int targetAngle           = 90;
int servoSpeed            = 10;      // мс задержка между шагами
bool servoMoving          = false;
bool servoAscending       = false;
bool servoPausing         = false;
unsigned long lastServoTs = 0;
unsigned long pauseStart  = 0;

// По умолчанию для MQTT
const int defaultAngle = 10;
const int defaultSpeed = 10;

// Компоненты
WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);
Servo servo;

// ====== Декларации ======
void setupWiFi();
void setupMQTT();
void connectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void setupWebServer();
void handleRelayCommand(int idx, const String& cmd);
void publishRelayStatus(int idx);
float readVoltage();
void adcTask();
void handleServoCommand(int angle, int speed);
void servoTask();

// ====== Setup ======
void setup() {
    Serial.begin(115200);
    randomSeed(analogRead(0));
    // Реле
    for (uint8_t i = 0; i < relayCount; ++i) {
        pinMode(relayPins[i], OUTPUT);
        digitalWrite(relayPins[i], LOW);
    }
    // Сервопривод
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    ESP32PWM::allocateTimer(2);
    ESP32PWM::allocateTimer(3);
    servo.setPeriodHertz(50);
    servo.attach(servoPin, 500, 2400);
    servo.write(currentAngle);

    setupWiFi();
    setupMQTT();
    setupWebServer();
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) setupWiFi();
    if (!mqtt.connected()) connectMQTT();
    mqtt.loop();
    server.handleClient();
    adcTask();
    servoTask();
    // Таймеры реле
    for (uint8_t i = 0; i < relayCount; ++i) {
        if (relayTimers[i] && millis() >= relayTimers[i]) {
            digitalWrite(relayPins[i], LOW);
            relayTimers[i] = 0;
            publishRelayStatus(i);
        }
    }
}

// ====== WiFi ======
void setupWiFi() {
    WiFiManager wm;
    if (!wm.autoConnect("ESP32-Relay6CH-Setup")) {
        ESP.restart();
    }
}

// ====== MQTT ======
void setupMQTT() {
    mqtt.setServer(mqttHostDefault, mqttPortDefault);
    mqtt.setCallback(mqttCallback);
}

void connectMQTT() {
    while (!mqtt.connected()) {
        if (mqtt.connect("ESP32Relay6CH", mqttUserDefault, mqttPasswordDefault)) {
            for (uint8_t i = 0; i < relayCount; ++i)
                mqtt.subscribe((String(baseTopic) + "/Door_" + String(i+1)).c_str());
            mqtt.subscribe((String(baseTopic) + "/Servo").c_str());
        } else {
            delay(5000);
        }
    }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    String msg;
    for (unsigned int i = 0; i < length; ++i) msg += (char)payload[i];
    String t = String(topic);
    if (t.startsWith(String(baseTopic) + "/Door_")) {
        int ch = t.substring(t.lastIndexOf('_') + 1).toInt() - 1;
        handleRelayCommand(ch, msg);
    } else if (t == String(baseTopic) + "/Servo") {
        int speed = defaultSpeed;
        int angle = defaultAngle;
        int idxS = msg.indexOf("speed:");
        int idxA = msg.indexOf("Angle:");
        if (idxS >= 0) speed = msg.substring(idxS + 6).toInt();
        if (idxA >= 0) angle = msg.substring(idxA + 6).toInt();
        handleServoCommand(angle, speed);
    }
}

// ====== Web-интерфейс ======
const char* htmlPage = R"rawliteral(
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>ESP32 Relay6CH</title></head>
<body>
<h3>Relay Control</h3>
Duration <input id="dur" type="number" value="10"/><br/>
<div id="r"></div>
<hr/>
<h3>Servo Control</h3>
Angle <input id="ang" type="number" value="10"/><br/>
Speed <input id="spd" type="number" value="10"/><br/>
<button onclick="s()">Go</button>
<script>
function r(ch,t){fetch(`/relay?ch=${ch}&t=${t}`);} 
function s(){let a=document.getElementById('ang').value, v=document.getElementById('spd').value; fetch(`/servo?angle=${a}&speed=${v}`);} 
window.onload=()=>{let d=document.getElementById('dur'),c=document.getElementById('r'); for(let i=1;i<=6;i++) c.innerHTML+=`<button onclick="r(${i},${d.value})">R${i} ON</button><button onclick="r(${i},0)">R${i} OFF</button><br/>`;};
</script>
</body>
</html>
)rawliteral";

void setupWebServer() {
    server.on("/", HTTP_GET, [](){ server.send(200, "text/html", htmlPage); });
    server.on("/relay", HTTP_GET, [](){ int ch = server.arg("ch").toInt() - 1; handleRelayCommand(ch, server.arg("t")); server.send(200, "application/json", "{\"ok\":1}"); });
    server.on("/servo", HTTP_GET, [](){ handleServoCommand(server.arg("angle").toInt(), server.arg("speed").toInt()); server.send(200, "application/json", "{\"ok\":1}"); });
    server.begin();
}

// ====== Реле ======
void handleRelayCommand(int idx, const String& cmd) {
    if (idx < 0 || idx >= relayCount) return;
    if (cmd == "0") { digitalWrite(relayPins[idx], LOW); relayTimers[idx] = 0; }
    else { digitalWrite(relayPins[idx], HIGH); relayTimers[idx] = millis() + cmd.toInt() * 1000; }
    publishRelayStatus(idx);
}

void publishRelayStatus(int idx) {
    StaticJsonDocument<128> doc;
    doc["state"] = digitalRead(relayPins[idx]) ? "ON" : "OFF";
    doc["voltage"] = readVoltage();
    char buf[128]; size_t n = serializeJson(doc, buf);
    mqtt.publish((String(baseTopic) + "/Door_" + String(idx+1) + "/info").c_str(), buf, n);
}

// ====== АЦП ======
float readVoltage(){ int r = analogRead(A0); return r * (3.3 / 4095) * (12 / 3.3); }

void adcTask() { if (millis() - lastAdcTs < adcInterval) return; lastAdcTs = millis(); StaticJsonDocument<64> d; d["voltage"] = readVoltage(); char b[64]; size_t n = serializeJson(d, b); mqtt.publish((String(baseTopic) + "/Voltage/info").c_str(), b, n); }

// ====== Серво ======
void handleServoCommand(int angle, int speed) {
    targetAngle    = 90 - angle;
    servoSpeed     = max(1, speed);
    servoMoving    = true;
    servoAscending = false;
    servoPausing   = false;
    lastServoTs    = millis();
}

void servoTask() {
    if (!servoMoving) return;
    unsigned long now = millis();
    if (now - lastServoTs < (unsigned long)servoSpeed) return;
    lastServoTs = now;
    if (!servoAscending) {
        if (currentAngle > targetAngle) {
            currentAngle--;
            servo.write(currentAngle);
            return;
        }
        if (!servoPausing) {
            servoPausing = true;
            pauseStart = now;
            return;
        }
        if (now - pauseStart < 1000) {
            return;
        }
        servoAscending = true;
        return;
    }
    if (currentAngle < 90) {
        currentAngle++;
        servo.write(currentAngle);
    } else {
        servoMoving = false;
        StaticJsonDocument<64> doc;
        doc["angle"] = currentAngle;
        doc["speed"] = servoSpeed;
        char buf[64]; size_t n = serializeJson(doc, buf);
        mqtt.publish((String(baseTopic) + "/Servo/info").c_str(), buf, n);
    }
}

