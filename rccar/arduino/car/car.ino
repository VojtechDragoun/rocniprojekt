/*
  car.ino – Arduino UNO (servo steering only)
  ===========================================

  Servo zapojení:
  - signál (oranžový/žlutý) -> D3
  - +5V -> 5V (ideálně externí 5V zdroj, UNO často nestačí)
  - GND -> GND (společná zem s externím zdrojem)

  Příkazy přes Serial (posílá Flask):
    STEER:L   -> vlevo (center - 45°)
    STEER:R   -> vpravo (center + 45°)
    STEER:C   -> střed (0° v logice ovládání)
*/

#include <Arduino.h>
#include <Servo.h>

static const int SERVO_PIN = 3;

// Kalibrace středu (tohle je tvoje "0°")
static const int SERVO_CENTER_DEG = 90;

// Offset do stran (±45°)
static const int SERVO_OFFSET_DEG = 45;

static const int SERVO_LEFT_DEG  = SERVO_CENTER_DEG - SERVO_OFFSET_DEG;   // 45
static const int SERVO_RIGHT_DEG = SERVO_CENTER_DEG + SERVO_OFFSET_DEG;   // 135

Servo steering;
String lineBuf;

void steerCenter() { steering.write(constrain(SERVO_CENTER_DEG, 0, 180)); }
void steerLeft()   { steering.write(constrain(SERVO_LEFT_DEG,   0, 180)); }
void steerRight()  { steering.write(constrain(SERVO_RIGHT_DEG,  0, 180)); }

bool handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return false;

  // očekáváme jen STEER:...
  if (cmd.startsWith("STEER:")) {
    String a = cmd.substring(6);
    a.trim();
    a.toUpperCase();

    if (a == "L") { steerLeft();   Serial.println("[OK] STEER:L"); return true; }
    if (a == "R") { steerRight();  Serial.println("[OK] STEER:R"); return true; }
    if (a == "C") { steerCenter(); Serial.println("[OK] STEER:C"); return true; }

    return false;
  }

  return false;
}

void setup() {
  Serial.begin(115200);
  delay(200);

  steering.attach(SERVO_PIN);
  steerCenter();

  Serial.println("=== Arduino UNO servo control ready ===");
  Serial.println("Commands: STEER:L, STEER:R, STEER:C");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n') {
      lineBuf.replace("\r", "");

      bool ok = handleCommand(lineBuf);
      if (!ok) {
        Serial.print("[ERR] Unknown cmd: ");
        Serial.println(lineBuf);
      }

      lineBuf = "";
    } else {
      if (lineBuf.length() < 80) lineBuf += c;
    }
  }
}