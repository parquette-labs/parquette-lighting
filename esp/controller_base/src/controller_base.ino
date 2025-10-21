#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <SparkFun_Qwiic_Keypad_Arduino_Library.h>
#include <SparkFun_Qwiic_Button.h>
#include <SparkFun_Qwiic_Joystick_Arduino_Library.h>
#include <MicroOscUdp.h>

#include <Adafruit_seesaw.h>
#include <seesaw_neopixel.h>

#define ENC_SWITCH 24
#define ENC_NEOPIX 6

#define SEESAW_ADDR_ENC1 0x36

Adafruit_seesaw enc1;
seesaw_NeoPixel enc1_pixel = seesaw_NeoPixel(1, ENC_NEOPIX, NEO_GRB + NEO_KHZ800);

int32_t enc1_position;

#define QWIIC_ADDR_REDBTN 0x6F

QwiicButton red_button;

#define ROT_WHEEL_SWITCH_SELECT 1
#define ROT_WHEEL_SWITCH_UP     2
#define ROT_WHEEL_SWITCH_LEFT   3
#define ROT_WHEEL_SWITCH_DOWN   4
#define ROT_WHEEL_SWITCH_RIGHT  5

#define SEESAW_ADDR_ROT_WHEEL 0x49

Adafruit_seesaw rot_wheel;
int32_t rot_wheel_position;

#define QWIIC_ADDR_JOYSTICK 0x21
JOYSTICK joystick;

#define QWIIC_ADDR_KEYPAD 0x4B
KEYPAD keypad;

#define WIFI_RECONNECT_INTERVAL 4000
unsigned long last_wifi_reconnect = millis();
bool wifi_connected = false;

const IPAddress outIp(192, 168, 88, 88);
WiFiUDP udp;
MicroOscUdp<1024> oscEndpoint(&udp, outIp, 5005);

// typedef struct {
// 	void (*connect_callback)(sensor_t*);
// 	void (*callback)(sensor_t*);
// 	void* object;
// 	bool flag;
// 	bool connected;
// 	uint8_t i2c_addr;
// 	uint16_t interval;
// 	uint16_t offset;
// } sensor_t;

// sensor_t sensors[] = {
// 	{
// 		.callback = &trigger_temp_conversion,
// 		.connect_callback = &trigger_temp_conversion,
// 		.flag = false,
// 		.connected = false,
// 		.interval = 500,
// 		.offset = 0,
// 	},
// };

// const uint16_t num_sensors = sizeof(sensors) / sizeof(sensor_t);

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

void wifi_connect() {
	WiFi.mode(WIFI_STA);
	WiFi.begin("purple24", "red-black-white-green");

	Serial.print("Connecting to WiFi ...");
	for (uint8_t i = 0; i < 25 && WiFi.status() != WL_CONNECTED; i++) {
		Serial.print('.');
		delay(500);
	}

	Serial.println("");

	Serial.print("WiFi Connected, assigned IP: ");
	Serial.println(WiFi.localIP());

	wifi_connected = WiFi.status() == WL_CONNECTED;

	udp.begin(5007);
}

void wifi_reconnect() {
	unsigned long current_millis = millis();

	if (!wifi_connected && WiFi.status() == WL_CONNECTED) {
		Serial.println("Successfully reconnected WiFi");
	}

	if ((WiFi.status() != WL_CONNECTED) && (current_millis - last_wifi_reconnect >= WIFI_RECONNECT_INTERVAL)) {
		Serial.println("Trying to reconnecting to WiFi...");
		WiFi.disconnect();
		WiFi.reconnect();
		last_wifi_reconnect = current_millis;
	}

	wifi_connected = WiFi.status() == WL_CONNECTED;
}

// void led_btn_setup(sensor_t* sensor) {
// 	(QwiicButton*)sensor->object
// 	red_button.begin(QWIIC_ADDR_REDBTN)

// }

// void led_btn_sensor(void) {

// }

void setup() {
	Serial.begin(115200);
	
	Wire.begin();

	wifi_connect();

	//check if red_button will acknowledge over I2C
	if (!red_button.begin(QWIIC_ADDR_REDBTN) || !joystick.begin(Wire, QWIIC_ADDR_JOYSTICK) || !keypad.begin(Wire, QWIIC_ADDR_KEYPAD)) {
		Serial.println("Device did not acknowledge! Freezing.");
		while(1) delay(10);
	}
	Serial.println("Button acknowledged.");
	red_button.LEDoff();  //start with the LED off

	Serial.println("Looking for seesaw!");

	if (!enc1.begin(SEESAW_ADDR_ENC1) || !enc1_pixel.begin(SEESAW_ADDR_ENC1) || !rot_wheel.begin(SEESAW_ADDR_ROT_WHEEL)) {
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

	version = ((rot_wheel.getVersion() >> 16) & 0xFFFF);
	if (version  != 5740){
	  Serial.print("Wrong firmware loaded? ");
	  Serial.println(version);
	  while(1) delay(10);
	}
	Serial.println("Found Product 5740");

	rot_wheel.pinMode(ROT_WHEEL_SWITCH_UP, INPUT_PULLUP);
	rot_wheel.pinMode(ROT_WHEEL_SWITCH_DOWN, INPUT_PULLUP);
	rot_wheel.pinMode(ROT_WHEEL_SWITCH_LEFT, INPUT_PULLUP);
	rot_wheel.pinMode(ROT_WHEEL_SWITCH_RIGHT, INPUT_PULLUP);
	rot_wheel.pinMode(ROT_WHEEL_SWITCH_SELECT, INPUT_PULLUP);

	// get starting position
	rot_wheel_position = rot_wheel.getEncoderPosition();

	Serial.println("Turning on interrupts");
	rot_wheel.enableEncoderInterrupt();
	rot_wheel.setGPIOInterrupts((uint32_t)1 << ROT_WHEEL_SWITCH_UP, 1);

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
		red_button.LEDconfig(250, 1000, 100);
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

	if (! rot_wheel.digitalRead(ROT_WHEEL_SWITCH_UP)) {
		Serial.println("UP pressed!");
	}
	if (! rot_wheel.digitalRead(ROT_WHEEL_SWITCH_DOWN)) {
		Serial.println("DOWN pressed!");
	}
	if (! rot_wheel.digitalRead(ROT_WHEEL_SWITCH_SELECT)) {
		Serial.println("SELECT pressed!");

		// OSCMessage msg("/test");

		// myOsc.sendInt("/test", 123);

		// udp.beginPacket(outIp, 1337);
		// udp.write('a');
		// udp.endPacket();
		oscEndpoint.sendMessage("/stuff", "i", (int32_t) 12);


		rgbLedWrite(RGB_BUILTIN, RGB_BRIGHTNESS, 0, 0);  // Red
		delay(250);
		rgbLedWrite(RGB_BUILTIN, 0, RGB_BRIGHTNESS, 0);  // Green
		delay(250);
		rgbLedWrite(RGB_BUILTIN, 0, 0, RGB_BRIGHTNESS);  // Blue
		delay(250);
		rgbLedWrite(RGB_BUILTIN, 0, 0, 0);  // Off / black

	}
	if (! rot_wheel.digitalRead(ROT_WHEEL_SWITCH_LEFT)) {
		Serial.println("LEFT pressed!");
	}
	if (! rot_wheel.digitalRead(ROT_WHEEL_SWITCH_RIGHT)) {
		Serial.println("RIGHT pressed!");
	}

	new_position = rot_wheel.getEncoderPosition();
	// did we move around?
	if (rot_wheel_position != new_position) {
		Serial.println(new_position);         // display new position
		rot_wheel_position = new_position;      // and save for next round
	}

	uint16_t x = joystick.getHorizontal();
	uint16_t y = joystick.getVertical();
	uint16_t b = joystick.getButton();

	bool joystick_active = false;


	if (!(x > 510 && x < 530)) {
		joystick_active = true;
		Serial.print("X: ");
		Serial.print((int32_t) x);

		oscEndpoint.sendMessage("/joystick_x", "i", (int32_t) x);
	}

	if (!(y > 510 && y < 530)) {
		joystick_active = true;
		Serial.print("Y: ");
		Serial.print((int32_t) y);

		oscEndpoint.sendMessage("/joystick_y", "i", (int32_t) y);
	}

	if (b != 1) {
		joystick_active = true;
		Serial.print("Button: ");
		Serial.print(b);
	}

	if (joystick_active) {
		Serial.println("");
	}

	keypad.updateFIFO();
	char keypad_button = keypad.getButton();

	if (keypad_button != 0) {
		Serial.println(keypad_button);
	}

	wifi_reconnect();

	// don't overwhelm serial port
	delay(10);
}
