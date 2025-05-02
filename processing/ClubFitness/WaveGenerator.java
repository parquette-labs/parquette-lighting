import processing.core.PApplet;

public class WaveGenerator extends Generator {

	public enum Shape {
		TRIANGLE,
		SQUARE,
		SIN
	}

	Shape shape;

	public WaveGenerator(PApplet p, String name, Shape shape, float amp, int phase, int period) {
		super(p, name, amp, phase, period);
		this.shape = shape;
	}

	public float value(int millis) {
		if (shape == Shape.TRIANGLE) {
			int modtime = ((millis+phase) % period);
			if (modtime < (period / 2)) {
				return p.map(modtime, 0.0f, period/2.0f, 0.0f, amp);
			} else {
				return p.map(modtime-period/2, 0.0f, period/2, amp, 0.0f);
			}
		} else if (shape == Shape.SQUARE) {
			int modtime = ((millis+phase) % period);
			if (modtime < (period / 2)) {
				return amp;
			} else {
				return 0.0f;
			}
		} else if (shape == Shape.SIN) {
			return amp * (p.sin((float)(millis+phase) / period * 2 * p.PI)*0.5f+0.5f);
		}

		return 0;
	}

}
