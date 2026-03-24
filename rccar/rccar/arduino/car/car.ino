/*
  car.ino
  =======

  Tenhle soubor je pro Arduino UNO.
  Řeší:
  - servo na zatáčení
  - ESC na motor

  Příkazy chodí přes Serial, typicky z app.py nebo jiného Python souboru.

  Příkazy:
    STEER:L
    STEER:R
    STEER:C
    THROTTLE:ON
    THROTTLE:OFF

  Zapojení:
    servo -> D3
    ESC   -> D5
*/

#include <Arduino.h>
#include <Servo.h>

// pin pro servo řízení
const int SERVO_PIN = 3;

// pin pro ESC od motoru
const int ESC_PIN = 5;


// střed serva = kola rovně
const int CENTER = 90;

// o kolik stupňů se zatáčí od středu
const int OFFSET = 45;


// minimální signál pro ESC = motor vypnutý
const int MOTOR_OFF = 1000;

// slabší roztočení motoru
const int MOTOR_ON = 1200;


// objekt pro servo zatáčení
Servo steering;

// objekt pro ESC
Servo esc;


// sem se bude postupně ukládat příchozí příkaz ze serialu
String buffer = "";


// nastaví kola rovně
void steerCenter() {
  steering.write(CENTER);
}


// zatočí doleva
void steerLeft() {
  steering.write(CENTER - OFFSET);
}


// zatočí doprava
void steerRight() {
  steering.write(CENTER + OFFSET);
}


// vypne motor
void motorOff() {
  esc.writeMicroseconds(MOTOR_OFF);
}


// zapne motor na slabší výkon
void motorOn() {
  esc.writeMicroseconds(MOTOR_ON);
}


// tahle funkce zpracuje textový příkaz
// když ho zná, provede akci a vrátí true
// když ho nezná, vrátí false
bool handleCommand(String cmd) {
  // odstranění mezer a konců řádku okolo textu
  cmd.trim();

  // prázdný příkaz ignorujeme
  if (cmd.length() == 0) return false;

  // zatáčení
  if (cmd.startsWith("STEER:")) {
    // vezmeme část za STEER:
    String val = cmd.substring(6);

    // pro jistotu odstraníme mezery
    val.trim();

    // převedeme na velká písmena
    val.toUpperCase();

    // levá
    if (val == "L") {
      steerLeft();
      Serial.println("[OK] L");
      return true;
    }

    // pravá
    if (val == "R") {
      steerRight();
      Serial.println("[OK] R");
      return true;
    }

    // střed
    if (val == "C") {
      steerCenter();
      Serial.println("[OK] C");
      return true;
    }

    // když je za STEER něco jiného než L/R/C
    return false;
  }

  // zapnutí motoru
  if (cmd == "THROTTLE:ON") {
    motorOn();
    Serial.println("[OK] ON");
    return true;
  }

  // vypnutí motoru
  if (cmd == "THROTTLE:OFF") {
    motorOff();
    Serial.println("[OK] OFF");
    return true;
  }

  // neznámý příkaz
  return false;
}


// setup se spustí jen jednou po startu Arduina
void setup() {
  // spuštění serial komunikace
  Serial.begin(115200);

  // připojení serva na pin D3
  steering.attach(SERVO_PIN);

  // připojení ESC na pin D5
  esc.attach(ESC_PIN);

  // po startu nastavíme kola rovně
  steerCenter();

  // a motor necháme vypnutý
  motorOff();

  // ESC často potřebuje chvíli na inicializaci
  delay(3000);

  // zpráva do serialu, že je Arduino připravené
  Serial.println("ready");
}


// loop běží pořád dokola
void loop() {
  // dokud jsou nějaká data ve serialu, čteme je
  while (Serial.available() > 0) {
    char c = Serial.read();

    // když přijde konec řádku, příkaz je celý
    if (c == '\n') {
      // odstraníme případné \r
      buffer.replace("\r", "");

      // zkusíme příkaz provést
      if (!handleCommand(buffer)) {
        // pokud se nepovedl, vypíšeme chybu
        Serial.print("ERR: ");
        Serial.println(buffer);
      }

      // vyčistíme buffer pro další příkaz
      buffer = "";
    } else {
      // jinak přidáváme znaky do bufferu
      // limit 80 znaků je jen jednoduchá ochrana
      if (buffer.length() < 80) {
        buffer += c;
      }
    }
  }
}