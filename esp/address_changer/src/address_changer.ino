#include <Wire.h>
#include "SparkFun_Qwiic_Joystick_Arduino_Library.h"
JOYSTICK joystick;

#define ADDR 0x20

void setup() {
    Serial.begin(9600);
    Serial.println("Qwiic Joystick Example");

    if(joystick.begin(Wire, ADDR) == false) {
        Serial.println("Joystick does not appear to be connected.");
        while(true) delay(10);
    } else {
        Serial.print("Address: 0x");
        Serial.print(ADDR, HEX);
        Serial.print(" Version: ");
        Serial.println(joystick.getVersion());
    }
}

void loop() {
    if (joystick.setI2CAddress(0x21) == true) {
        Serial.print("Firmware: ");
        Serial.println(joystick.getVersion());
    }

    while(true) delay(10);
}
