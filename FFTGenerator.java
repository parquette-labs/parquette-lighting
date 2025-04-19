import processing.core.PApplet;

public class FFTGenerator extends Generator {

  int memoryLength;
  int subdivisions;
  float[] weighting;
  int[] stamps;
  float[][] memory;
  float thres;

  public FFTGenerator(PApplet p, String name, float amp, int subdivisions, int memoryLength) {
    super(p, name, amp, 0, 0);
    this.subdivisions = subdivisions;
    weighting = new float[subdivisions];
    setMemory(memoryLength);
    stamps = new int[memoryLength];
    setThreadshold(0);
  }

  public void forward(float[] values, int millis) {
    for (int i = 1; i < stamps.length; i++) {
    	stamps[i] = stamps[i-1];
    }

    stamps[0] = millis;

    for (int k = memoryLength-1; k >= 0; k--) {
	    if (k != 0) p.arraycopy(memory[k-1], memory[k]);
    }

    for (int i = 0; i < subdivisions; i++) {
      memory[0][i] = values[i]*weighting[i];

      if (memory[0][i] < thres) {
        memory[0][i] = 0;
      } else {
        memory[0][i] -= thres;
      }
    }
  }

  public float[] getWeighting() {
  	return weighting;
  }

  public void setWeights(float[] weighting) {
  	p.arraycopy(weighting, this.weighting);
  }

  public void setThreadshold(float thres) {
    this.thres = thres;
  }

  public void setMemory(int memoryLength) {
    this.memoryLength = memoryLength;
    memory = new float[memoryLength][subdivisions];
  }

  public float value(int millis) {
  	int bestIndex = -1;
  	for (int i = 0; i < stamps.length; i++) {
  		if (bestIndex == -1) {
  			bestIndex = i;
  			continue;
  		}

  		float best = p.abs(stamps[bestIndex] - millis);
  		float curr = p.abs(stamps[i] - millis);
  		if (curr < best) bestIndex = i;
  	}

  	float sum = 0.0f;
  	for (int i = 0; i < memory[0].length; i++) {
  		sum += memory[bestIndex][i];
  	}
  	return sum*amp;
  }
}
