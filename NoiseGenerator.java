import processing.core.PApplet;
import java.lang.Math;

public class NoiseGenerator extends Generator {

	float lastValue;
	int lastMillis;

	public NoiseGenerator(PApplet p, float amp, int phase, int period) {
		super(p, amp, phase, period);
	}

	public float value(int millis) {
		if (millis % (period * 2) > period) {
			lastValue = (float)Math.random() * amp;
			lastMillis = millis;
		} 

		return lastValue;
	}

}
