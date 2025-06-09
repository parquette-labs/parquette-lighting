# Parquette Lighting 🏋️‍♀️🕺🪩🕺🏋️‍♀️

## Notes/Ideas/TODOs
* Setup Raspberry Pi
* Redundancy, RTFM and manual
* Presets mechanism
* Add all black button
* Easy UI for punch and other interactives with no misclick risk
* FFT bands selectors don't appear to be working properly 
* Timing / race condition with the threading causing punch issues and latency issues
* Bug with adjusting the period of osciallators causing jump
* FWD/BACK memory slice needs the memory slices to be log spaced or similar, e.g. more slices at the short time scale and fewer slices at the long timescale
* Typing in new code and error catching in OSC
* Account for relative brightness of lights
* Time averaging of FFT to substract and do bg removal on the FFT
* Sync values on load
* Wave generators should be able to switch shapes without rewiring in the patchbay
* Reimplement tempo button
* Nudge button of some kind for certain values, e.g. period / freq
* FFTs should also be able to swap slicing without rewiring? Or some better mechanism for swapping behavior
* Auto detection for low/high intensity of music that can trigger mode changes or similar
* Parameter LFO / preset or mode LFO
* Validate if we can reconfigure audio and dmx on the fly
* Accounting for incandescent delay
* Add floor / ceil / scaling instead of just offest and mult for chans
* Switch to dual spectrograms for harmonic and percussive, run beat detection, mel scale via librosa
* Annotate FFT with key freqs
* Beat matching / calculation
* Patterns that are tempo locked
* Can I move the mapping definitions for output mix into the front end fully?
* Auto load channel and generator names from the front end or scrupting to sync between front and backend
* Align stutter automatically to beat quantization
