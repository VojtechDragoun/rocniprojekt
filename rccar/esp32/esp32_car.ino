#include <Arduino.h>

// ---------------------- DC motor (H-bridge) ----------------------
static const int MOTOR_IN1_PIN = 26;
static const int MOTOR_IN2_PIN = 27;
static const int MOTOR_PWM_PIN = 25;

static const int MOTOR_PWM_CHANNEL  = 0;
static const int MOTOR_PWM_FREQ_HZ  = 20000;
static const int MOTOR_PWM_RES_BITS = 8;   // 0..255

// ---------------------- Stepper (A4988/DRV8825) -------------------
static const int STEPPER_STEP_PIN = 33;
static const int STEPPER_DIR_PIN  = 32;
static const int STEPPER_EN_PIN   = 14;

static const bool USE_STEPPER_ENABLE = true;
static const bool STEPPER_ENABLE_LOW_ACTIVE = true;

// Jak daleko je 45° v krocích?
// ZÁLEŽÍ NA:
// - motoru (typicky 200 kroků/otáčku)
// - microsteppingu (1/1, 1/8, 1/16, 1/32)
// - převodu / mechanice mezi krokáčem a volantem
// Musíš to doladit testem.
static const long STEER_STEPS_FOR_45DEG = 400; // <-- UPRAV PODLE REALITY

// Bezpečnostní limit, aby sis neutrhl mechaniku
static const long STEER_MAX_POS_STEPS = 1200;

static const float STEPPER_MAX_STEPS_PER_SEC = 1200.0f;

volatile long g_stepperPos = 0;
volatile long g_stepperTarget = 0;
volatile bool g_stepperStop = false;
unsigned long g_lastStepMicros = 0;

void stepperEnable(bool en) {
  if (!USE_STEPPER_ENABLE) return;
  if (STEPPER_ENABLE_LOW_ACTIVE) digitalWrite(STEPPER_EN_PIN, en ? LOW : HIGH);
  else                          digitalWrite(STEPPER_EN_PIN, en ? HIGH : LOW);
}

long clampSteerPos(long pos) {
  if (pos > STEER_MAX_POS_STEPS) return STEER_MAX_POS_STEPS;
  if (pos < -STEER_MAX_POS_STEPS) return -STEER_MAX_POS_STEPS;
  return pos;
}

void stepperSetTarget(long targetSteps) {
  g_stepperTarget = clampSteerPos(targetSteps);
  g_stepperStop = false;
  stepperEnable(true);
}

void stepperStopNow() {
  g_stepperStop = true;
  stepperEnable(true);
}

void stepperUpdate() {
  if (g_stepperStop) return;

  long pos = g_stepperPos;
  long target = g_stepperTarget;

  if (pos == target) return;

  bool dirForward = (target > pos);
  digitalWrite(STEPPER_DIR_PIN, dirForward ? HIGH : LOW);

  const unsigned long stepIntervalUs = (unsigned long)(1000000.0f / STEPPER_MAX_STEPS_PER_SEC);

  unsigned long now = micros();
  if (now - g_lastStepMicros < stepIntervalUs) return;
  g_lastStepMicros = now;

  digitalWrite(STEPPER_STEP_PIN, HIGH);
  delayMicroseconds(3);
  digitalWrite(STEPPER_STEP_PIN, LOW);

  if (dirForward) g_stepperPos++;
  else            g_stepperPos--;
}

// ---------------------- Motor control ----------------------------
void motorApply(char dir, int pwm) {
  if (pwm < 0) pwm = 0;
  if (pwm > 255) pwm = 255;

  if (dir == 'S' || pwm == 0) {
    ledcWrite(MOTOR_PWM_CHANNEL, 0);
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);
    return;
  }

  if (dir == 'F') {
    digitalWrite(MOTOR_IN1_PIN, HIGH);
    digitalWrite(MOTOR_IN2_PIN, LOW);
  } else if (dir == 'B') {
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, HIGH);
  } else {
    ledcWrite(MOTOR_PWM_CHANNEL, 0);
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);
    return;
  }

  ledcWrite(MOTOR_PWM_CHANNEL, pwm);
}

// ---------------------- Serial command handling ------------------
bool handleCommand(String lineRaw) {
  String line = lineRaw;
  line.trim();
  if (line.length() == 0) return false;

  // 1) W:1 / W:0
  if (line.startsWith("W:")) {
    int v = line.substring(2).toInt();
    if (v == 1) {
      motorApply('F', 255); // max výkon
      Serial.println("[OK] W=1 -> Motor FWD 255");
    } else {
      motorApply('S', 0);   // stop
      Serial.println("[OK] W=0 -> Motor STOP");
    }
    return true;
  }

  // 2) STEER:L / STEER:R / STEER:C
  if (line.startsWith("STEER:")) {
    String arg = line.substring(6);
    arg.trim();
    arg.toUpperCase();

    if (arg == "L") {
      stepperSetTarget(-STEER_STEPS_FOR_45DEG);
      Serial.println("[OK] STEER:L -> target -45deg");
      return true;
    }
    if (arg == "R") {
      stepperSetTarget(+STEER_STEPS_FOR_45DEG);
      Serial.println("[OK] STEER:R -> target +45deg");
      return true;
    }
    if (arg == "C") {
      stepperSetTarget(0);
      Serial.println("[OK] STEER:C -> target center");
      return true;
    }
    if (arg == "STOP") {
      stepperStopNow();
      Serial.println("[OK] STEER:STOP");
      return true;
    }
    return false;
  }

  // (Volitelně) pořád můžeš podporovat starý protokol M:... / ST:...
  // ale teď to není nutné.

  return false;
}

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(MOTOR_IN1_PIN, OUTPUT);
  pinMode(MOTOR_IN2_PIN, OUTPUT);
  pinMode(MOTOR_PWM_PIN, OUTPUT);

  ledcSetup(MOTOR_PWM_CHANNEL, MOTOR_PWM_FREQ_HZ, MOTOR_PWM_RES_BITS);
  ledcAttachPin(MOTOR_PWM_PIN, MOTOR_PWM_CHANNEL);
  motorApply('S', 0);

  pinMode(STEPPER_STEP_PIN, OUTPUT);
  pinMode(STEPPER_DIR_PIN, OUTPUT);
  digitalWrite(STEPPER_STEP_PIN, LOW);

  if (USE_STEPPER_ENABLE) {
    pinMode(STEPPER_EN_PIN, OUTPUT);
    stepperEnable(true);
  }

  g_stepperPos = 0;
  g_stepperTarget = 0;
  g_stepperStop = false;

  Serial.println("=== ESP32 RCcar ready (W/A/D control) ===");
  Serial.println("Commands:");
  Serial.println("  W:1 / W:0");
  Serial.println("  STEER:L / STEER:R / STEER:C");
}

void loop() {
  stepperUpdate();

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.replace("\r", "");
    bool ok = handleCommand(line);
    if (!ok) {
      Serial.printf("[ERR] invalid cmd: %s\n", line.c_str());
    }
  }

  delay(1);
}
