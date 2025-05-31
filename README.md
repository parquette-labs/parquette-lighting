# Parquette Lighting 🏋️‍♀️🕺🪩🕺🏋️‍♀️

## Notes/Ideas/TODOs
* Must do
	* Finish hooking up all control surfaces
	* Hook up FFT and if possible switch to librosa audio 
	* Weightings needed?
	* Add controls for the tungsten spot
	* fft port error
* Immediate ideas
	* General presets with a way to cycle between them
	* typing in new code and error catching in OSC
	* Add new modes for the 2 new lights
	* End to end test
	* Reimplement temp button
	* Add all black
	* FFT fwd stop
	* Manually match default values in front end
* Future ideas
	* auto load chan and gen names to sync between front and backend
	* Sync values on load
	* Auto match default values
	* Check if we can reconfigure on the fly
	* Use psychoacoustic scale for FFT, display with log binning
	* Accounting for incandescent delay
	* Add floor / ceil / scaling instead of just offest for chans
	* Mode LFO and/or intensity driven mode switcher
	* Remote for impule and mode change
	* Switch to dual spectrograms for harmonic and percussive, run beat detection, mel scale via librosa
	* Annotate FFT with freqs
	* Beat matching / calculation
	* Can I move the mapping definitions for output mix into the front end fully?