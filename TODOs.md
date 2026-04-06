# Notes/Ideas/TODOs

* Top
	* BPM phase calc
	* Button to set the periods of the waves same as BPM
	* Add fog machine

* Presets, automations and controls
	* Interpolate between presets when you switch over
	* All input values from the OSC sliders should be smoothed slightly via a parameter defined in click in seconds. Default should be 0.1s smoothing.
* Math problems
	* The FWD/BACK memory slice needs the memory slices to be log spaced or similar, e.g. more slices at the short time scale and fewer slices at the long timescale. This might be impossible if we're only computing every 10ms or so
	* Bug with adjusting the period of osciallators causing jump
* Bugs
	* Timing / race condition with the threading causing punch issues and latency issues
	* Validate if we can reconfigure audio and dmx on the fly
* Light perception
	* Overall and per light brightness perception map
* BPM detection
	* BPM phase calc is still very dubious
	* Way to connect BPM to the other effects
* FFT 
	* Time averaging of FFT to substract and do bg removal on the FFT
	* FFTs should also be able to swap slicing without rewiring? Or some better mechanism for swapping behavior, similar to idea with waves
	* Annotate FFT with key freqs
* New ideas
	* Optimize compute by idyling FFT and BPM when there is no audio and/or no interaction for multiple days
	* Use inheritance from parent frame to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
	* Some type of sequencer source
	* Auto detection for low/high intensity of music that can trigger mode changes or similar
	* Blue/green deploy mechanism
	* Spinning mode
	* Movement patterns for the spots
	* Switch to dual spectrograms for harmonic and percussive
	* Wave generators should be able to switch shapes without rewiring in the patchbay? Or general rethink of the patchbay
	* Can I move the mapping definitions for output mix into the front end fully?
	* Auto load channel and generator names from the front end or scrupting to sync between front and backend
	* It would be cool to have some smoothing or softening for hits, e.g. BPM or FFT, so it feels more organic and less sharp. In particular for example the BPM blip wash mode could be softer
