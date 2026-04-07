# Untested

* XY Tilt
* Hazer
* Adjust levels with real input
* Impulse
* DMX pass

# Notes/Ideas/TODOs

* Need a working offset calculator for the BPM
* Annotate FFT plots in the front end with key frequencies
* Some type of sequencer source both for short, medium and long term scheduling. Perhaps a long term scheduler is different
* Some kind of orchestrator based on the metrics of music type
* Some kind of scheduler for the orchestrator
* Spinning mode similar to fwd / zig zag
* All input values from the OSC sliders should be smoothed slightly via a parameter defined in click in seconds. Default should be 0.1s smoothing.
* Overall and per light brightness perception map and limits
* Can I use inheritance from parent frame in open stage control to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
* Blue/green deploy mechanism
* Movement patterns drivers for the spots
* Generator modes vs patchbay
	* Wave generators should be able to switch shapes without rewiring in the patchbay? Or general rethink of the patchbay
	* FFTs should also be able to swap slicing without rewiring? Or some better mechanism for swapping behavior, similar to idea with waves
