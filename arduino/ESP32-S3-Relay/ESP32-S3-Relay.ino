#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// ======== GLOBAL CONFIG ========
// Wi-Fi / MQTT defaults
const char* default_ssid         = "DIR-825-ORiA";
const char* default_password     = "Domobox485";
const char* default_mqtt_server  = "192.168.1.100";
const uint16_t default_mqtt_port = 1883;
const char* default_mqtt_user    = "";
const char* default_mqtt_pass    = "";
const unsigned long WIFI_TIMEOUT = 20000;

// AP-mode
const char* ap_ssid     = "ESP32_Config";
const char* ap_password = "config1234";

// GPIO pins
const int relayPin1 = 1;
const int relayPin2 = 2;
const int adcPin1   = 34;
const int adcPin2   = 35;
const int pinLED_R  = 16;
const int pinLED_G  = 17;
const int pinLED_B  = 18;
const int servoPin  = 9;    // PWM for servo

// Voltage divider
const float R1_1 = 100000.0, R2_1 = 33000.0;
const float R1_2 = 100000.0, R2_2 = 33000.0;

// Timing
const unsigned long relayOnDuration = 2000;
const unsigned long publishInterval  =   1000;

// ======== STATE VARIABLES ========
Preferences    prefs;
WebServer      server(80);
WiFiClient     wifiClient;
PubSubClient   mqtt(wifiClient);
Servo          myServo;

// Wi-Fi/MQTT settings
String wifiSSID, wifiPassword;
String mqttServer;
uint16_t mqttPort;
String mqttUser, mqttPass;
bool   wifiConnected = false;
bool   mqttConnected = false;

// Relay state
bool   door1Active = false;
bool   door2Active = false;
unsigned long door1Ts = 0;
unsigned long door2Ts = 0;

// ADC publish
unsigned long lastPub1 = 0;
unsigned long lastPub2 = 0;

// ======== SERVO FSM ========
enum ServoState {
  IDLE,
  MOVING_DOWN,
  PAUSE_BOTTOM,
  MOVING_UP,
  PAUSE_TOP
};
static ServoState servoState   = IDLE;
static bool       servoActive  = false;
static bool       servoOneShot = false;
unsigned long     stateTs      = 0;
int               bottomAngle  = 0;
int               topAngle     = 90;
int               stepDelay    = 20;
int               currentAngle = 90;

// ======== HELPERS ========
void setLED(bool r, bool g, bool b) {
  digitalWrite(pinLED_R, r ? HIGH:LOW);
  digitalWrite(pinLED_G, g ? HIGH:LOW);
  digitalWrite(pinLED_B, b ? HIGH:LOW);
}
void updateLED() {
  if (!wifiConnected)        setLED(true, false, false);
  else if (!mqttConnected)   setLED(false,false,true);
  else                        setLED(false,true,false);
}
float readVin(int ch) {
  int pin = (ch==1?adcPin1:adcPin2);
  float R1 = (ch==1?R1_1:R1_2), R2 = (ch==1?R2_1:R2_2);
  analogRead(pin); delayMicroseconds(50);
  const int N=10; long sum=0;
  for(int i=0;i<N;i++){ sum+=analogRead(pin); delay(5);}
  float Vadc = (sum/float(N))/4095.0*3.3;
  return Vadc*(R1+R2)/R2;
}
void publishDoorStats() {
  char buf[32];
  if (mqttConnected) {
    if (millis()-lastPub1 >= publishInterval) {
      lastPub1 = millis();
      snprintf(buf,sizeof(buf),"%.2f",readVin(1));
      mqtt.publish("ESP/Relay6CH/Door_1_Stat", buf, true);
    }
    if (millis()-lastPub2 >= publishInterval) {
      lastPub2 = millis();
      snprintf(buf,sizeof(buf),"%.2f",readVin(2));
      mqtt.publish("ESP/Relay6CH/Door_2_Stat", buf, true);
    }
  }
}
bool connectMQTT() {
  if (mqtt.connected()) return true;
  String clientId = "ESP32-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  bool ok = mqttUser.length()
            ? mqtt.connect(clientId.c_str(), mqttUser.c_str(), mqttPass.c_str())
            : mqtt.connect(clientId.c_str());
  if (!ok) {
    mqttConnected = false; updateLED();
    return false;
  }
  mqttConnected = true; updateLED();
  mqtt.subscribe("ESP/Relay6CH/Open_1_Door");
  mqtt.subscribe("ESP/Relay6CH/Open_2_Door");
  mqtt.subscribe("ESP/ServoRemote");
  return true;
}
void mqttCB(char* topic, byte* payload, unsigned int len) {
  String msg;
  for(unsigned i=0;i<len;i++) msg += (char)payload[i];
  if (String(topic)=="ESP/ServoRemote") {
    if      (msg=="1") { servoActive=true;  servoOneShot=false;  servoState=IDLE;  stateTs=millis(); myServo.attach(servoPin);    mqtt.publish("ESP/ServoRemote/status","running",true);}
    else if (msg=="0") { servoActive=false; servoOneShot=false;  servoState=IDLE;  myServo.write(90); delay(200); myServo.detach(); mqtt.publish("ESP/ServoRemote/status","stopped",true);}
    else if (msg=="2") { servoActive=false; servoOneShot=true;   servoState=IDLE;  stateTs=millis(); myServo.attach(servoPin);    mqtt.publish("ESP/ServoRemote/status","oneshot",true);}
  }
  else if (String(topic)=="ESP/Relay6CH/Open_1_Door" && msg=="1" && !door1Active) {
    digitalWrite(relayPin1, LOW); door1Active=true; door1Ts=millis();
  }
  else if (String(topic)=="ESP/Relay6CH/Open_2_Door" && msg=="1" && !door2Active) {
    digitalWrite(relayPin2, LOW); door2Active=true; door2Ts=millis();
  }
}

// ======== WEB CONFIG ========
String pageConfig(bool ap) {
  String p="<html><body><h3>ESP32 Configuration</h3><form action='/save' method='POST'>";
  p+="SSID:<input name='ssid' value='"+wifiSSID+"'><br>";
  p+="Pass:<input name='password' value='"+wifiPassword+"'><br>";
  p+="MQTT srv:<input name='mqtt_server' value='"+mqttServer+"'><br>";
  p+="MQTT port:<input name='mqtt_port' value='"+String(mqttPort)+"'><br>";
  p+="MQTT usr:<input name='mqtt_user' value='"+mqttUser+"'><br>";
  p+="MQTT pwd:<input name='mqtt_pass' value='"+mqttPass+"'><br>";
  p+="<button>Save</button></form>";
  if(!ap) p+="<p>IP:"+WiFi.localIP().toString()+" <a href='/reconfig'>Reconfig</a></p>";
  p+="</body></html>";
  return p;
}
void handleRoot()    { bool ap = !wifiConnected && WiFi.getMode()==WIFI_AP; server.send(200,"text/html",pageConfig(ap)); }
void handleSave() {
  if(server.hasArg("ssid")&&server.hasArg("password")&&server.hasArg("mqtt_server")&&server.hasArg("mqtt_port")&&server.hasArg("mqtt_user")&&server.hasArg("mqtt_pass")){
    prefs.begin("cfg",false);
    prefs.putString("wifiSSID", server.arg("ssid"));
    prefs.putString("wifiPassword", server.arg("password"));
    prefs.putString("mqttServer", server.arg("mqtt_server"));
    prefs.putUInt("mqttPort", server.arg("mqtt_port").toInt());
    prefs.putString("mqttUser", server.arg("mqtt_user"));
    prefs.putString("mqttPass", server.arg("mqtt_pass"));
    prefs.end();
    server.send(200,"text/html","<h3>Saved, rebooting...</h3>");
    delay(1000); ESP.restart();
  } else server.send(400,"text/plain","Missing params");
}
void handleReconfig() {
  server.send(200,"text/html","<h3>Switching to AP...</h3>");
  delay(500);
  WiFi.disconnect(true);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ap_ssid, ap_password);
  wifiConnected = false; updateLED();
}

// ======== SERVO FSM HANDLER ========
void servoFSM() {
  unsigned long now = millis();
  auto pubInfo = [&](int ang,int d){
    char b[64]; snprintf(b,64,"{\"angle\":%d,\"delay\":%d}",ang,d);
    mqtt.publish("ESP/ServoInfo", b, false);
  };

  switch(servoState) {
    case IDLE:
      if (servoActive || servoOneShot) {
        bottomAngle = random(5,10);
        stepDelay   = random(10,30);
        stateTs     = now;
        currentAngle=90;
        myServo.write(currentAngle);
        servoState  = MOVING_DOWN;
      }
      break;

    case MOVING_DOWN:
      if (now - stateTs >= (unsigned)stepDelay) {
        stateTs = now;
        currentAngle = max(currentAngle-1, bottomAngle);
        myServo.write(currentAngle);
        pubInfo(currentAngle, stepDelay);
        if (currentAngle <= bottomAngle) {
          servoState = PAUSE_BOTTOM;
          stateTs    = now;
        }
      }
      break;

    case PAUSE_BOTTOM:
      if (now - stateTs >= 1000) {
        servoState = MOVING_UP;
        stateTs    = now;
      }
      break;

    case MOVING_UP:
      if (now - stateTs >= (unsigned)stepDelay) {
        stateTs = now;
        currentAngle = min(currentAngle+1, topAngle);
        myServo.write(currentAngle);
        pubInfo(currentAngle, stepDelay);
        if (currentAngle >= topAngle) {
          servoState = PAUSE_TOP;
          stateTs    = now;
        }
      }
      break;

    case PAUSE_TOP:
      if (now - stateTs >= (servoActive? 5000 : 0)) {
        if (servoActive) {
          // next cycle
          bottomAngle = random(5,10);
          stepDelay   = random(10,30);
          servoState  = MOVING_DOWN;
          stateTs     = now;
        } else {
          // finish
          myServo.detach();
          mqtt.publish("ESP/ServoRemote/status","stopped",true);
          servoOneShot = false;
          servoState   = IDLE;
        }
      }
      break;
  }
}

// ======== SETUP ========
void setup() {
  Serial.begin(115200);
  prefs.begin("cfg", true);
  wifiSSID    = prefs.getString("wifiSSID", "");
  wifiPassword= prefs.getString("wifiPassword", "");
  mqttServer  = prefs.getString("mqttServer", "");
  mqttPort    = prefs.getUInt("mqttPort", 0);
  mqttUser    = prefs.getString("mqttUser", "");
  mqttPass    = prefs.getString("mqttPass", "");
  prefs.end();

  if (wifiSSID.isEmpty())    wifiSSID    = default_ssid, wifiPassword = default_password;
  if (mqttServer.isEmpty()||mqttPort==0) mqttServer = default_mqtt_server, mqttPort = default_mqtt_port;

  pinMode(relayPin1, OUTPUT); digitalWrite(relayPin1, HIGH);
  pinMode(relayPin2, OUTPUT); digitalWrite(relayPin2, HIGH);
  pinMode(pinLED_R, OUTPUT);
  pinMode(pinLED_G, OUTPUT);
  pinMode(pinLED_B, OUTPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(adcPin1, ADC_11db);
  analogSetPinAttenuation(adcPin2, ADC_11db);

  randomSeed(analogRead(adcPin1));
  myServo.attach(servoPin);
  myServo.write(90);

  // Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSSID.c_str(), wifiPassword.c_str());
  unsigned long start = millis();
  while (millis()-start < WIFI_TIMEOUT && WiFi.status()!=WL_CONNECTED) delay(100);
  wifiConnected = (WiFi.status()==WL_CONNECTED);
  if (!wifiConnected) WiFi.softAP(ap_ssid, ap_password);

  // Web server
  server.on("/",        HTTP_GET,  handleRoot);
  server.on("/save",    HTTP_POST, handleSave);
  server.on("/reconfig", HTTP_GET,  handleReconfig);
  server.begin();

  // MQTT
  mqtt.setServer(mqttServer.c_str(), mqttPort);
  mqtt.setCallback(mqttCB);
  if (wifiConnected) connectMQTT();

  updateLED();
}

// ======== MAIN LOOP ========
void loop() {
  server.handleClient();
  unsigned long now = millis();

  // MQTT reconnect
  if (wifiConnected && !mqtt.connected() && now - lastPub1 > 5000) {
    connectMQTT();
  }
  if (mqtt.connected()) mqtt.loop();

  // Relay timing
  if (door1Active && now - door1Ts >= relayOnDuration) {
    digitalWrite(relayPin1, HIGH); door1Active=false;
  }
  if (door2Active && now - door2Ts >= relayOnDuration) {
    digitalWrite(relayPin2, HIGH); door2Active=false;
  }

  publishDoorStats();
  servoFSM();
}
