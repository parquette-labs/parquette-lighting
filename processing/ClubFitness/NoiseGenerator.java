import processing.core.PApplet;
import java.lang.Math;

public class NoiseGenerator extends Generator {

	float lastValue;
	int lastMillis;

	public NoiseGenerator(PApplet p, String name, float amp, int phase, int period) {
		super(p, name, amp, phase, period);
	}

	public float value(int millis) {
		if (millis % (period * 2) > period) {
			lastValue = (float)Math.random() * amp;
			lastMillis = millis;
		} 

		return lastValue;
	}

}
