/*
  car.ino
  =======

  Tenhle soubor je program pro Arduino UNO.

  Hlavní úkoly souboru:
  - ovládání serva pro zatáčení
  - ovládání ESC / motoru
  - možnost měnit úhel zatáčení podle vybraného auta
  - možnost měnit hodnotu pro zapnutí motoru z webové aplikace

  Arduino přijímá textové příkazy přes Serial.
  Tyto příkazy typicky posílá Python backend přes soubor arduino_comm.py.

  Příklady podporovaných příkazů:
    STEER:L
    STEER:R
    STEER:C
    THROTTLE:ON
    THROTTLE:OFF
    STEER_ANGLE:45
    MOTOR_ON_VALUE:1250

  Zapojení:
    servo -> D3
    ESC   -> D5
*/

#include <Arduino.h>
/*
  Arduino.h je základní Arduino knihovna.
  Obsahuje běžné funkce a typy jako:
  - pinMode
  - digitalWrite
  - delay
  - Serial
  - String
  - constrain
*/

#include <Servo.h>
/*
  Servo.h slouží pro práci se servem a také s ESC,
  protože ESC se často ovládá stejným signálem jako servo.
*/


// ------------------------------------------------------------
// PINY
// ------------------------------------------------------------

// pin pro servo řízení
const int SERVO_PIN = 3;

// pin pro ESC od motoru
const int ESC_PIN = 5;


// ------------------------------------------------------------
// NASTAVENÍ ŘÍZENÍ
// ------------------------------------------------------------

// střed serva = kola rovně
// většina klasických serv má střed okolo 90°
const int CENTER = 90;

// aktuální úhel zatáčení od středu
// tahle hodnota se může měnit podle auta vybraného v aplikaci
int steerOffset = 45;


// ------------------------------------------------------------
// NASTAVENÍ MOTORU
// ------------------------------------------------------------

// minimální signál pro ESC = motor vypnutý
const int MOTOR_OFF = 1000;

// hodnota pro zapnutí motoru
// tohle už není konstanta, ale proměnná,
// protože si ji uživatel může změnit z dashboardu
int motorOnValue = 1200;


// ------------------------------------------------------------
// OBJEKTY
// ------------------------------------------------------------

// objekt pro servo zatáčení
Servo steering;

// objekt pro ESC motoru
Servo esc;


// ------------------------------------------------------------
// BUFFER PRO PŘÍKAZY
// ------------------------------------------------------------

// sem se bude postupně ukládat příchozí řádek ze serialu
String buffer = "";


// ------------------------------------------------------------
// POMOCNÉ FUNKCE
// ------------------------------------------------------------

bool isDigitsOnly(String s) {
  /*
    Ověří, jestli řetězec obsahuje jen číslice.

    Používá se u příkazů jako:
    - STEER_ANGLE:45
    - MOTOR_ON_VALUE:1250

    Díky tomu si zkontrolujeme,
    že za dvojtečkou opravdu přišlo číslo.
  */

  // odstranění mezer a konců řádků na začátku a konci
  s.trim();

  // prázdný string určitě není validní číslo
  if (s.length() == 0) return false;

  // projdeme všechny znaky
  for (unsigned int i = 0; i < s.length(); i++) {
    if (!isDigit(s[i])) {
      // jakmile najdeme nečíselný znak, vracíme false
      return false;
    }
  }

  // pokud všechny znaky byly číslice, je to v pořádku
  return true;
}


void setSteerAngle(int angle) {
  /*
    Nastaví aktuální úhel zatáčení.

    angle = o kolik stupňů od středu se má zatáčet.

    constrain(angle, 0, 90) zajistí,
    že hodnota nebude mimo bezpečný rozsah.
  */

  steerOffset = constrain(angle, 0, 90);
}


void steerCenter() {
  /*
    Nastaví servo do středu.
    Auto tedy pojede rovně.
  */
  steering.write(CENTER);
}


void steerLeft() {
  /*
    Zatočí doleva o aktuálně nastavený úhel.
    Např. když steerOffset = 45,
    servo se nastaví na 90 - 45 = 45.
  */
  steering.write(CENTER - steerOffset);
}


void steerRight() {
  /*
    Zatočí doprava o aktuálně nastavený úhel.
    Např. když steerOffset = 45,
    servo se nastaví na 90 + 45 = 135.
  */
  steering.write(CENTER + steerOffset);
}


void setMotorOnValue(int value) {
  /*
    Nastaví hodnotu pro zapnutí motoru.

    Povolený rozsah:
    1200 až 1300

    Pokud by přišla menší nebo větší hodnota,
    constrain ji automaticky omezí.
  */
  motorOnValue = constrain(value, 1200, 1300);
}


void motorOff() {
  /*
    Vypne motor.
    ESC dostane minimální hodnotu.
  */
  esc.writeMicroseconds(MOTOR_OFF);
}


void motorOn() {
  /*
    Zapne motor podle aktuálně nastavené hodnoty.

    Hodnota motorOnValue se může měnit za běhu,
    třeba z dashboardu.
  */
  esc.writeMicroseconds(motorOnValue);
}


// ------------------------------------------------------------
// ZPRACOVÁNÍ PŘÍKAZŮ
// ------------------------------------------------------------

bool handleCommand(String cmd) {
  /*
    Zpracuje jeden textový příkaz.

    Vrací:
    - true  = příkaz byl rozpoznán a proveden
    - false = příkaz nebyl platný nebo nebyl známý
  */

  // odstranění mezer a konců řádků okolo textu
  cmd.trim();

  // prázdný příkaz ignorujeme
  if (cmd.length() == 0) return false;

  // ----------------------------------------------------------
  // ZMĚNA ÚHLU ZATÁČENÍ
  // ----------------------------------------------------------
  if (cmd.startsWith("STEER_ANGLE:")) {
    /*
      Příklad:
      STEER_ANGLE:45
    */

    // vezmeme text za "STEER_ANGLE:"
    String val = cmd.substring(12);
    val.trim();

    // pokud to není čisté číslo, příkaz je neplatný
    if (!isDigitsOnly(val)) {
      return false;
    }

    // převod na číslo
    int angle = val.toInt();

    // nastavení nového úhlu
    setSteerAngle(angle);

    // odpověď do serial monitoru
    Serial.print("[OK] ANGLE=");
    Serial.println(steerOffset);

    return true;
  }

  // ----------------------------------------------------------
  // ZMĚNA HODNOTY MOTOR_ON
  // ----------------------------------------------------------
  if (cmd.startsWith("MOTOR_ON_VALUE:")) {
    /*
      Příklad:
      MOTOR_ON_VALUE:1250
    */

    // text "MOTOR_ON_VALUE:" má 15 znaků
    String val = cmd.substring(15);
    val.trim();

    if (!isDigitsOnly(val)) {
      return false;
    }

    int value = val.toInt();

    // nastavení nové hodnoty pro motor
    setMotorOnValue(value);

    Serial.print("[OK] MOTOR_ON_VALUE=");
    Serial.println(motorOnValue);

    return true;
  }

  // ----------------------------------------------------------
  // ZATÁČENÍ
  // ----------------------------------------------------------
  if (cmd.startsWith("STEER:")) {
    /*
      Podporované příkazy:
      STEER:L
      STEER:R
      STEER:C
    */

    String val = cmd.substring(6);
    val.trim();
    val.toUpperCase();

    if (val == "L") {
      steerLeft();
      Serial.println("[OK] L");
      return true;
    }

    if (val == "R") {
      steerRight();
      Serial.println("[OK] R");
      return true;
    }

    if (val == "C") {
      steerCenter();
      Serial.println("[OK] C");
      return true;
    }

    return false;
  }

  // ----------------------------------------------------------
  // MOTOR
  // ----------------------------------------------------------
  if (cmd == "THROTTLE:ON") {
    motorOn();
    Serial.println("[OK] ON");
    return true;
  }

  if (cmd == "THROTTLE:OFF") {
    motorOff();
    Serial.println("[OK] OFF");
    return true;
  }

  // pokud se sem program dostane,
  // příkaz nebyl rozpoznán
  return false;
}


// ------------------------------------------------------------
// SETUP
// ------------------------------------------------------------

void setup() {
  /*
    setup() se spustí jednou po startu Arduina.
    Tady se provede základní inicializace.
  */

  // spuštění serial komunikace
  // musí odpovídat rychlosti v Pythonu
  Serial.begin(115200);

  // připojení serva na pin D3
  steering.attach(SERVO_PIN);

  // připojení ESC na pin D5
  esc.attach(ESC_PIN);

  // nastavíme výchozí úhel zatáčení
  setSteerAngle(45);

  // nastavíme výchozí hodnotu pro motor
  setMotorOnValue(1200);

  // kola nastavíme rovně
  steerCenter();

  // motor necháme vypnutý
  motorOff();

  // ESC často po zapnutí potřebuje chvíli na inicializaci
  delay(3000);

  // zpráva do serialu, že je Arduino připravené
  Serial.println("ready");
}


// ------------------------------------------------------------
// LOOP
// ------------------------------------------------------------

void loop() {
  /*
    loop() běží pořád dokola.

    Tady neustále kontrolujeme,
    jestli z Pythonu nepřišel nový znak přes serial.
  */

  while (Serial.available() > 0) {
    // načteme jeden znak
    char c = Serial.read();

    // konec řádku znamená, že příkaz je kompletní
    if (c == '\n') {
      // odstranění případného carriage return
      buffer.replace("\r", "");

      // zkusíme příkaz zpracovat
      if (!handleCommand(buffer)) {
        // pokud se nepovedl, vypíšeme chybu
        Serial.print("ERR: ");
        Serial.println(buffer);
      }

      // vyčištění bufferu pro další příkaz
      buffer = "";
    } else {
      // jinak znak přidáme do bufferu
      // limit délky je jednoduchá ochrana proti přetečení
      if (buffer.length() < 80) {
        buffer += c;
      }
    }
  }
}