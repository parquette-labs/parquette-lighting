import javax.sound.midi.*;

import uk.co.xfactorylibrarians.coremidi4j.CoreMidiDeviceProvider;

import ddf.minim.*;
import ddf.minim.analysis.*;
import controlP5.*;
import dmxP512.*;
import processing.serial.*;
import themidibus.*; //Import the library

// ------ Audio ------ //

int smallest_octave = 22; //Controls subdivisions
int octave_bands = 3; //Controls subdivisions
int subdivisions; //Number of FFT subdivisions

int x_offset = 100; //Left and right padding size
int default_y = 10; //Base Y size
int default_z = 0; //Base Z Size

float scale_y = 30; //Y size multiplies
float scale_z = 0; //Z size multiplier

int default_recession = 0; //Z recession

boolean symm = false; //Mirror frequencies with memory
boolean fade = true; //Fade with memory

int frame_drop = 1; //5 is cool

int memory_length = 7; //Number of overlapping frames drawn to screen
float[][] memory; //FFT data, stored for 
float[] weighting; //Ajust for precieved sound levels

float thres = 0; //2 is cool

color bgr_color = color(0,0,0);
color forground_color = color(255,255,255);

Minim minim;
FFT fft;
 AudioInput in; // Comment this out to use and audio file
//AudioPlayer in; // Uncomment this to use an audio file

ControlP5 controlP5;
boolean show_controls = false;

boolean show_envelope = false;
color envelope_color = color(255,192,203);

float constant = 40;

// ------ DMX ------ //

DmxP512 dmxOutput;

String DMXPRO_PORT = "/dev/tty.usbserial-EN264168";
int DMXPRO_BAUDRATE = 115200;

int LEFT_RED_ADDR = 1;
int RIGHT_RED_ADDR = 5;

int[] dmxValues = new int[8];

// ------ Midi ------ //

MidiBus midiBus; // The MidiBus

Generator[] generators;

NoiseGenerator noise1;
NoiseGenerator noise2;
WaveGenerator wave1;
WaveGenerator wave2;
WaveGenerator wave3;
ImpulseGenerator impulse;
ImpulseGenerator fft1;
ImpulseGenerator fft2;

CheckBox checkbox;

float[] channels = new float[10];

void setup() {
  // ------ Graphics ------ //

  size(1500, 800);

  noise1 = new NoiseGenerator(this, "Noise1", 1, 0, 1000);
  noise2 = new NoiseGenerator(this, "Noise2", 1, 0, 1000);
  wave1 = new WaveGenerator(this, "SIN1", WaveGenerator.Shape.SIN, 255, 0, 1000);
  wave2 = new WaveGenerator(this, "SQ1", WaveGenerator.Shape.SQUARE, 255, 500, 1000);
  wave3 = new WaveGenerator(this, "TRI1", WaveGenerator.Shape.TRIANGLE, 255, 0, 1000);
  impulse = new ImpulseGenerator(this, "Impulse", 1.0, 500, 10, 3, 0.75f);
  fft1 = new ImpulseGenerator(this, "FFT1", 1.0, 500, 10, 3, 0.75f);
  fft2 = new ImpulseGenerator(this, "FFT2", 1.0, 500, 10, 3, 0.75f);

  generators = new Generator[] {
    noise1,
    noise2,
    wave1,
    wave2,
    wave3,
    impulse,
    fft1,
    fft2,
  };

   //fullScreen(P3D);

  background(bgr_color);

  noFill();
  stroke(forground_color);
  strokeWeight(1);
  
  smooth();
  perspective();
  
  rectMode(CENTER);
  
  controlP5 = new ControlP5(this);
  
  ControlGroup controls = controlP5.addGroup("Controls",50,50,750);
  
  controlP5.addBang("Symm",10,10,10,10).setGroup(controls);
  controlP5.addBang("Fade",75,10,10,10).setGroup(controls);
  
  controlP5.addSlider("Y scale",0,150,scale_y,150,10,10,250).setGroup(controls);
  controlP5.addSlider("Z scale",0,150,scale_z,225,10,10,250).setGroup(controls);
  controlP5.addSlider("Z recesion",0,100,default_recession,300,10,10,250).setGroup(controls);
  
  controlP5.addSlider("Frame Drop",1,30,frame_drop,375,10,10,250).setGroup(controls);
  controlP5.addSlider("Memory Length",1,70,memory_length,450,10,10,250).setGroup(controls);
  controlP5.addSlider("Threshold",0,20,thres,525,10,10,250).setGroup(controls);
  
  controlP5.addSlider("L0",0, 255, 0, 10, 350, 10, 250).setGroup(controls);
  controlP5.addSlider("L1",0, 255, 0, 60, 350, 10, 250).setGroup(controls);
  controlP5.addSlider("L2",0, 255, 0, 110, 350, 10, 250).setGroup(controls);
  controlP5.addSlider("L3",0, 255, 0, 160, 350, 10, 250).setGroup(controls);

  checkbox = controlP5.addCheckBox("checkBox")
    .setPosition(300, 450)
    .setColorForeground(color(120))
    .setColorActive(color(255))
    .setSize(15, 15)
    .setItemsPerRow(channels.length)
    .setSpacingColumn(50)
    .setSpacingRow(12);

  for (int i = 0; i < generators.length*channels.length; i++) {
    checkbox.addItem("C"+i%channels.length+" "+generators[i/channels.length].getName(), i);
  }

  for (int i = 0; i < 10; i++) {
    for (int j = 0; j < 10; j++) {
      int x = 200;
      int y = 350;
      controlP5.addRadioButton("X"+i+"Y"+j).setGroup(controls).setSize(10, 10).setPosition(x + i * 12, y + j*12);
    }
  }

  ScrollableList default_weights = controlP5.addScrollableList("Weights",600,20,100,250);
  default_weights.setGroup(controls);
  default_weights.setLabel("Default Weights");
  default_weights.addItem("A Curve",0);
  default_weights.addItem("B Curve",0);
  default_weights.addItem("C Curve",0);
  default_weights.addItem("Linear",0);
  default_weights.addItem("Manual",0);
  default_weights.addItem("Neutral",0);

  controlP5.addSlider("Constant",0,250,constant,775,10,10,250).setGroup(controls);

  if(!show_controls) controlP5.hide();

  // ------ Audio ------ //
  
  minim = new Minim(this);
  
  in = minim.getLineIn(Minim.MONO); //Comment this out to use an audio file
  
  //in = minim.loadFile("song.mp3", 1024); // Uncomment this to use an audio file
  //in.loop(); // Uncomment this to use an audio file

  fft = new FFT(in.bufferSize(), in.sampleRate());
  fft.logAverages(smallest_octave, octave_bands);
  
  subdivisions = fft.avgSize();
  memory = new float[memory_length][subdivisions];
  
  weighting = new float[subdivisions];
  weighting = normalize(weigh_lin(smallest_octave, octave_bands, subdivisions));
  
  println("Subdivision Accuracy:");
  println("---------------");
  println("Smallest Octave - " + smallest_octave + " Hz");
  println("Octave Bands - " + octave_bands);
  println("Subdivisions - " + subdivisions);
  println();

  // ------ DMX ------ //

  try {
    dmxOutput = new DmxP512(this, dmxValues.length, false);
    dmxOutput.setupDmxPro(DMXPRO_PORT, DMXPRO_BAUDRATE);
    println("DMX setup done");
  }
  catch(Exception e) {
    println("Couldn't initialize your DMX interface, likely it's port is wrong or it's disconnected");
  }

  // ------ Midi ------ //

  MidiBus.list(); // List all available Midi devices on STDOUT. This will show each device's index and name.
  midiBus = new MidiBus(this, "CoreMIDI4J - Launchkey Mini MK3 MIDI Port", "CoreMIDI4J - Launchkey Mini MK3 MIDI Port"); // Create a new MidiBus with no input device and the default Java Sound Synthesizer as the output device.
}

void draw() {
  background(bgr_color);

  noFill();
  stroke(forground_color);
  strokeWeight(1);
  
  fft.forward(in.mix);
  
  for(int i = 0;i < subdivisions; i++) {
    memory[0][i] = fft.getAvg(i)*weighting[i];

    if(memory[0][i] < thres) {
      memory[0][i] = 0;
    } else {
      memory[0][i] -= thres;
    }
  }
  
  //Here we have OpenGL alpha interference, this could be solve by Z-axis sorting ... for now we'll stick to these options
  //for(int k = memory_length-1;k >= 0;k--) {  //Better for recession
  for(int k = 0;k < memory_length;k++) {   //Better For Overlap
    if(k%frame_drop == 0) {
      if(!fade || k==0) { 
        stroke(forground_color);
      } else {
        stroke(forground_color,255-(255/(memory_length)*k));
      }
    
      beginShape(QUADS);
      for(int i = 0;i < subdivisions;i++) {    
        if(i != 0) {
          // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y-(memory[k][i])*scale_y, default_z+(memory[k][i])*scale_z-k*default_recession);
          // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y+(memory[k][i])*scale_y, default_z+(memory[k][i])*scale_z-k*default_recession);
          vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y-(memory[k][i])*scale_y);
          vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y+(memory[k][i])*scale_y);
        }
    
        // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y, 0-k*default_recession);
        // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y+(memory[k][i])*scale_y, default_z+(memory[k][i])*scale_z-k*default_recession);
        // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y-(memory[k][i])*scale_y, default_z+(memory[k][i])*scale_z-k*default_recession);
        // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y, 0-k*default_recession);
        vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y);
        vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y+(memory[k][i])*scale_y);
        vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y-(memory[k][i])*scale_y);
        vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y);
    
        if(i != subdivisions) {
          vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y+(memory[k][i])*scale_y);
          vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y-(memory[k][i])*scale_y);
          // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2+default_y+(memory[k][i])*scale_y, default_z+(memory[k][i])*scale_z-k*default_recession);
          // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset, (float)height/2-default_y-(memory[k][i])*scale_y, default_z+(memory[k][i])*scale_z-k*default_recession);    
        }
      }
      endShape();
    }
  }
  
  //This is currently in a sperate loop from the drawing because of ongoing mods due to the z-axis transparency problems
  for(int k = memory_length-1;k >= 0;k--) {
    if(symm) {
      if(k != 0) arraycopy(reverse(memory[k-1]),memory[k]);
    } else {
      if(k != 0) arraycopy(memory[k-1],memory[k]);
    }
  }
  
  if(show_envelope) {
    stroke(envelope_color);
    if(mousePressed && !show_controls) {
      int i = 0;
      if(mouseX > x_offset && mouseX < width-x_offset) {
        i = constrain(round((float)(mouseX-x_offset)/((float)(width-x_offset*2)/(subdivisions-1))),0,subdivisions-1);
      } else if(mouseX > width-x_offset) {
        i = subdivisions-1;
      } else {
        i = 0;
      }
      weighting[i] = constrain((float)(height-mouseY)/height,0,1);
    }
    for(int i = 0;i < subdivisions;i++) {
      rect((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset,height-height*weighting[i],5,5);
    }
    beginShape();
    for(int i = 0;i < subdivisions;i++) {
      // vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset,height-height*weighting[i],0);
      vertex((float)(width-x_offset*2)/(subdivisions-1)*i+x_offset,height-height*weighting[i]);
    }
    endShape();
  }

  setRedLights(true, 0, (int)wave1.value(millis()));
  setRedLights(true, 1, (int)wave2.value(millis()));

  updateDMX();
}

void setRedLights(boolean left, int index, int value) {
  if (left) {
    dmxValues[LEFT_RED_ADDR-1+index] = value;
  } else {
    dmxValues[RIGHT_RED_ADDR-1+index] = value;
  }
}

void updateDMX() {
  if (dmxOutput == null) return;
  dmxOutput.set(1, dmxValues);
}

void noteOn(Note note) {
 // Receive a noteOn
 // println();
 // println("Note On:");
 // println("--------");
 // println("Channel:"+note.channel());
 // println("Pitch:"+note.pitch());
 // println("Velocity:"+note.velocity());
}

void noteOff(Note note) {
 // Receive a noteOff
 // println();
 // println("Note Off:");
 // println("--------");
 // println("Channel:"+note.channel());
 // println("Pitch:"+note.pitch());
 // println("Velocity:"+note.velocity());
}

void controllerChange(ControlChange change) {
 // Receive a controllerChange
 // println();
 // println("Controller Change:");
 // println("--------");
 // println("Channel:"+change.channel());
 // println("Number:"+change.number());
 // println("Value:"+change.value());
}

void controlEvent(ControlEvent theEvent) {

  if (theEvent.isFrom(checkbox)) {
    print("got an event from "+checkbox.getName()+"\t\n");
    // checkbox uses arrayValue to store the state of 
    // individual checkbox-items. usage:
    println(checkbox.getArrayValue());
    int col = 0;
    for (int i=0;i<checkbox.getArrayValue().length;i++) {
      int n = (int)checkbox.getArrayValue()[i];
      print(n);
    }
    println();    
    return;
  }

 if(theEvent.getController().getName() == "Symm") symm = !symm;
 if(theEvent.getController().getName() == "Fade") fade = !fade;

 if(theEvent.getController().getName() == "L0") setRedLights(true, 0, (int)theEvent.controller().getValue());
 if(theEvent.getController().getName() == "L1") setRedLights(true, 1, (int)theEvent.controller().getValue());
 if(theEvent.getController().getName() == "L2") setRedLights(true, 2, (int)theEvent.controller().getValue());
 if(theEvent.getController().getName() == "L3") setRedLights(true, 3, (int)theEvent.controller().getValue());

  
 if(theEvent.getController().getName() == "Y scale") scale_y = theEvent.controller().getValue();
 if(theEvent.getController().getName() == "Z scale") scale_z = theEvent.controller().getValue();
 if(theEvent.getController().getName() == "Z recesion") default_recession = round(theEvent.controller().getValue());
  
 if(theEvent.getController().getName() == "Frame Drop") frame_drop = round(theEvent.getController().getValue());
 if(theEvent.getController().getName() == "Memory Length") {
   memory_length = round(theEvent.controller().getValue());
   memory = new float[memory_length][subdivisions];
 }
 if(theEvent.getController().getName() == "Threshold") thres = theEvent.getController().getValue();
  
 if(theEvent.label() == "A Curve") weighting = normalize(weigh_A(smallest_octave, octave_bands, subdivisions));
 if(theEvent.label() == "B Curve") weighting = normalize(weigh_B(smallest_octave, octave_bands, subdivisions));
 if(theEvent.label() == "C Curve") weighting = normalize(weigh_C(smallest_octave, octave_bands, subdivisions));
 if(theEvent.label() == "Linear") weighting = normalize(weigh_lin(smallest_octave, octave_bands, subdivisions));
 if(theEvent.label() == "Manual") weighting = normalize(weigh_manual(smallest_octave, octave_bands, subdivisions));
 if(theEvent.label() == "Neutral") weighting = normalize(weigh_neutral(smallest_octave, octave_bands, subdivisions));

 if(theEvent.getController().getName() == "Constant") {
   constant = theEvent.getController().getValue();
   weighting = normalize(weigh_lin(smallest_octave, octave_bands, subdivisions));
 }
}

void keyPressed() {
  switch(key) {
    case 'c':
      show_controls = !show_controls;
      if(show_controls) {
        controlP5.show();
      } else {
        controlP5.hide();
      }
    break;
    case 'e':
      show_envelope = !show_envelope;
    break;
  }
}

void stop()
{
  println("Final Parameters:");
  println("---------------");
  println("Y scale - " + scale_y);
  println("Z scale - " + scale_z);
  println("Memory Length - " + memory_length);
  println("Default Recession - " + default_recession);
  println("Symmetry - " + symm);
  println("Fade - " + fade);
  println("Frame Drop - " + frame_drop);
  println("Threshold - " + thres);
  println();
  println("Final Gain:");
  println("---------------");
  for(int i = 0;i < weighting.length;i++) {
    println(i + ":" + weighting[i]);
  }
  println();
  //Always close Minim audio classes when you are done with them  
  in.close();
  minim.stop();
  //song.close();
  super.stop();
}

float[] normalize(float[] input) {
  float max_val = 0;
  for(int i = 0;i < input.length;i++) {
    if(input[i] > max_val) {
      max_val = input[i];
    }
  }
  for(int i = 0;i < input.length;i++) {
    input[i] = input[i]/max_val;
  }
  return input;
}

float[] weigh_A(int smallest_octave, int octave_bands, int subdivisions) {
  float[] new_weighting = new float[subdivisions];
  float lowest_octave = smallest_octave;
  float band_ratio = pow(2,(float)1/octave_bands);
  float freq;
  for (int i = 0;i < (subdivisions/octave_bands);i++) {
    for(int k = 0;k < octave_bands;k++) {
      freq = lowest_octave*pow(2,i)*pow(band_ratio,k);
      new_weighting[i*octave_bands+k] = pow(10,(2 + 20*log((pow(12200,2)*pow(freq,4))/((sq(freq)+sq(20.6))*sqrt((sq(freq)+sq(107.7))*(sq(freq)+sq(737.9)))*(sq(freq)+sq(12200))))/log(10))/10)+constant;
    }
  }
  return new_weighting;
}

float[] weigh_B(int smallest_octave, int octave_bands, int subdivisions) {
  float[] new_weighting = new float[subdivisions];
  float lowest_octave = smallest_octave;
  float band_ratio = pow(2,(float)1/octave_bands);
  float freq;
  for (int i = 0;i < (subdivisions/octave_bands);i++) {
    for(int k = 0;k < octave_bands;k++) {
      freq = lowest_octave*pow(2,i)*pow(band_ratio,k);
      new_weighting[i*octave_bands+k] = pow(10,(0.17 + 20*log((pow(12200,2)*pow(freq,3))/((sq(freq)+sq(20.6))*sqrt(sq(freq)+sq(158.5))*(sq(freq)+sq(12200))))/log(10))/10)+constant;
    }
  }
  
  return new_weighting;
}

float[] weigh_C(int smallest_octave, int octave_bands, int subdivisions) {
  float[] new_weighting = new float[subdivisions];
  float lowest_octave = smallest_octave;
  float band_ratio = pow(2,(float)1/octave_bands);
  float freq;
  for (int i = 0;i < (subdivisions/octave_bands);i++) {
    for(int k = 0;k < octave_bands;k++) {
      freq = lowest_octave*pow(2,i)*pow(band_ratio,k);
      new_weighting[i*octave_bands+k] = pow(10,(0.06 + 20*log((pow(12200,2)*pow(freq,2))/((sq(freq)+sq(20.6))*(sq(freq)+sq(12200))))/log(10))/10)+constant;
    }
  }
  
  return new_weighting;
}

float[] weigh_lin(int smallest_octave, int octave_bands, int subdivisions) {
  float[] new_weighting = new float[subdivisions];
  float lowest_octave = smallest_octave;
  float band_ratio = pow(2,(float)1/octave_bands);
  float freq,next_freq;
  for (int i = 0;i < (subdivisions/octave_bands);i++) {
    for(int k = 0;k < octave_bands;k++) {
      freq = lowest_octave*pow(2,i)*pow(band_ratio,k);
      next_freq = lowest_octave*pow(2,i)*pow(band_ratio,k+1);
      //if(k == (octave_bands-1)) next_freq = lowest_octave*pow(2,i+1);
      new_weighting[i*octave_bands+k] = abs(next_freq-freq)+constant;
    }
  }
  
  return new_weighting;
}

float[] weigh_neutral(int smallest_octave, int octave_bands, int subdivisions) {
  float[] new_weighting = new float[subdivisions];
  for (int i = 0;i < subdivisions;i++) {
      new_weighting[i] = 1;
  }
  return new_weighting;
}

float[] weigh_manual(int smallest_octave, int octave_bands, int subdivisions) {
  float[] new_weighting = new float[subdivisions];
  for (int i = 0;i < subdivisions;i++) {
    if(i <= subdivisions/2) {
      new_weighting[i] = 1/((((float)subdivisions/2)-i)/2+1);
    } else {
      new_weighting[i] = 1*(i-((float)subdivisions/2)+1);
    }
  }
  return new_weighting;
}
