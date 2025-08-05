# Parquette Lighting 🏋️‍♀️🕺🪩🕺🏋️‍♀️

## Notes/Ideas/TODOs
* Setup system on mac mini
* Redundancy, RTFM and manual
* UX
	* Special UI (or object) for punch and other common actions
	* Sync values on load
* Presets and automations
	* Presets mechanism
	* Add all black button
	* House lights button
	* Parameter LFO / preset or mode LFO
	* Auto detection for low/high intensity of music that can trigger mode changes or similar
* Math problems
	* Add floor / ceil / scaling instead of just offest and mult for chans
	* No negative values?
	* Adjust how master level works
	* Per chanel multiplier levels
	* FWD/BACK memory slice needs the memory slices to be log spaced or similar, e.g. more slices at the short time scale and fewer slices at the long timescale
	* Bug with adjusting the period of osciallators causing jump
* Bugs
	* Improve threading issues, can we run faster
	* Timing / race condition with the threading causing punch issues and latency issues
	* Validate if we can reconfigure audio and dmx on the fly
* Light perception
	* Overall and per light brightness perception map
* BPM detection
	* BPM confidence, auto disables BPM driven effects
	* Show BPM and BPM confidence
	* Improve BPM smoother
	* Way to connect BPM to the other effects
* FFT 
	* Time averaging of FFT to substract and do bg removal on the FFT
	* FFTs should also be able to swap slicing without rewiring? Or some better mechanism for swapping behavior, similar to idea with waves
	* Annotate FFT with key freqs
* New ideas
	* Spinning mode
	* Switch to dual spectrograms for harmonic and percussive
	* Wave generators should be able to switch shapes without rewiring in the patchbay?
	* Can I move the mapping definitions for output mix into the front end fully?
	* Auto load channel and generator names from the front end or scrupting to sync between front and backend
	* Align stutter automatically to beat quantization
