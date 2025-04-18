import processing.core.PApplet;

public class ImpulseGenerator extends Generator {

	int punchPointMillis;
	int duty;
	int echo;
	float echoDecay;

	public ImpulseGenerator(PApplet p, String name, float amp, int period, int duty, int echo, float echoDecay) {
		super(p, name, amp, 0, period);
		this.duty = duty;
		this.echo = echo;
		this.echoDecay = echoDecay;
	}

	public void punch(int millis) {
		punchPointMillis = millis;
	}

	public void setEcho(int echo, float echoDecay) {
		this.echo = echo;
		this.echoDecay = echoDecay;
	}

	public void setDuty(int duty) {
		this.duty = duty;
	}

	public float value(int millis) {
		int ellapse = millis - punchPointMillis;
		int count = ellapse / period;
		if (count > echo) return 0.0f;

		if (ellapse % period > 0 && ellapse % period < duty) {
			return amp * p.pow(echoDecay, count);
		} else {
			return 0.0f;
		}
	}

}
