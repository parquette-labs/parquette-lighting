#include <SparkFun_Qwiic_Button.h>

#include "Adafruit_seesaw.h"
#include <seesaw_neopixel.h>

#define ENC_SWITCH 24
#define ENC_NEOPIX 6

#define SEESAW_ADDR_ENC1 0x36

Adafruit_seesaw enc1;
seesaw_NeoPixel enc1_pixel = seesaw_NeoPixel(1, ENC_NEOPIX, NEO_GRB + NEO_KHZ800);

int32_t enc1_position;

QwiicButton red_button;
uint8_t brightness = 250;   //The maximum brightness of the pulsing LED. Can be between 0 (min) and 255 (max)
uint16_t cycleTime = 1000;   //The total time for the pulse to take. Set to a bigger number for a slower pulse, or a smaller number for a faster pulse
uint16_t offTime = 200;     //The total time to stay off between pulses. Set to 0 to be pulsing continuously.

void setup() {
	Serial.begin(115200);
	while (!Serial) delay(10);

	Serial.println("Qwiic red_button examples");
	Wire.begin(); //Join I2C bus

	//check if red_button will acknowledge over I2C
	if (red_button.begin(0x6F) == false) {
		Serial.println("Device did not acknowledge! Freezing.");
		while(1) delay(10);
	}
	Serial.println("Button acknowledged.");
	red_button.LEDoff();  //start with the LED off

	Serial.println("Looking for seesaw!");

	if (!enc1.begin(SEESAW_ADDR_ENC1) || !enc1_pixel.begin(SEESAW_ADDR_ENC1)) {
	Serial.println("Couldn't find seesaw on default address");
		while(1) delay(10);
	}
	Serial.println("seesaw started");

	uint32_t version = ((enc1.getVersion() >> 16) & 0xFFFF);
	if (version  != 4991){
		Serial.print("Wrong firmware loaded? ");
		Serial.println(version);
		while(1) delay(10);
	}
	Serial.println("Found Product 4991");

	delay(10);

	// set not so bright!
	enc1_pixel.setBrightness(20);
	enc1_pixel.show();

	// use a pin for the built in encoder switch
	enc1.pinMode(ENC_SWITCH, INPUT_PULLUP);

	// get starting position
	enc1_position = enc1.getEncoderPosition();

	Serial.println("Turning on interrupts");
	enc1.setGPIOInterrupts((uint32_t)1 << ENC_SWITCH, 1);
	enc1.enableEncoderInterrupt();
}

void loop() {
	//check if red_button is pressed, and tell us if it is!
	if (red_button.isPressed() == true) {
		Serial.println("The red_button is pressed!");
		red_button.LEDconfig(brightness, cycleTime, offTime);
		while (red_button.isPressed() == true)
			delay(10);  //wait for user to stop pressing
		Serial.println("The red_button is not pressed.");
		red_button.LEDoff();
	}

	if (!enc1.digitalRead(ENC_SWITCH)) {
		Serial.println("Button pressed!");
	}

	int32_t new_position = enc1.getEncoderPosition();
	// did we move arounde?
	if (enc1_position != new_position) {
		Serial.println(new_position);         // display new position

		// change the neopixel color
		enc1_pixel.setPixelColor(0, Wheel((new_position*4) & 0xFF));
		enc1_pixel.show();
		enc1_position = new_position;      // and save for next round
	}

	// don't overwhelm serial port
	delay(10);
}


uint32_t Wheel(byte WheelPos) {
	WheelPos = 255 - WheelPos;
	if (WheelPos < 85) {
		return enc1_pixel.Color(255 - WheelPos * 3, 0, WheelPos * 3);
	}
	if (WheelPos < 170) {
		WheelPos -= 85;
		return enc1_pixel.Color(0, WheelPos * 3, 255 - WheelPos * 3);
	}
	WheelPos -= 170;
	return enc1_pixel.Color(WheelPos * 3, 255 - WheelPos * 3, 0);
}

// ---- //

// /*
//   BlinkRGB

//   Demonstrates usage of onboard RGB LED on some ESP dev boards.

//   Calling digitalWrite(RGB_BUILTIN, HIGH) will use hidden RGB driver.

//   RGBLedWrite demonstrates control of each channel:
//   void rgbLedWrite(uint8_t pin, uint8_t red_val, uint8_t green_val, uint8_t blue_val)

//   WARNING: After using digitalWrite to drive RGB LED it will be impossible to drive the same pin
//     with normal HIGH/LOW level
// */
// //#define RGB_BRIGHTNESS 64 // Change white brightness (max 255)

// // the setup function runs once when you press reset or power the board

// void setup() {
//   // No need to initialize the RGB LED
// }

// // the loop function runs over and over again forever
// void loop() {
// #ifdef RGB_BUILTIN
//   digitalWrite(RGB_BUILTIN, HIGH);  // Turn the RGB LED white
//   delay(1000);
//   digitalWrite(RGB_BUILTIN, LOW);  // Turn the RGB LED off
//   delay(1000);

//   rgbLedWrite(RGB_BUILTIN, RGB_BRIGHTNESS, 0, 0);  // Red
//   delay(1000);
//   rgbLedWrite(RGB_BUILTIN, 0, RGB_BRIGHTNESS, 0);  // Green
//   delay(1000);
//   rgbLedWrite(RGB_BUILTIN, 0, 0, RGB_BRIGHTNESS);  // Blue
//   delay(1000);
//   rgbLedWrite(RGB_BUILTIN, 0, 0, 0);  // Off / black
//   delay(1000);
// #endif
// }