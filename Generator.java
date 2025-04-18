import processing.core.PApplet;

public abstract class Generator {

	PApplet p;
	float amp;
	int phase;
	int period;

	public Generator(PApplet p, float amp, int phase, int period) {
		this.p = p;
		this.amp = amp;
		this.phase = phase;
		this.period = period;
	}

	public void setAmp(float amp) {
		this.amp = amp;
	}

	public void setPhase(int phase) {
		this.phase = phase;
	}

	public void setPeriod(int period) {
		this.period = period;
	}

	public abstract float value(int millis);

}
