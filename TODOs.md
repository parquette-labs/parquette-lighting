# Untested

* XY Tilt
* Hazer
* Adjust levels with real input
* Impulse
* DMX passthrough
* Color fade in out

# Notes/Ideas/TODOs

* Add an interval to the hazer
* Need a working offset calculator for the BPM, was working ok before
* sq1, sq2, sq3, need to have separate period controls
* Move controls for synths next to patch bays
* Debug non SHED fixtures
* Annotate FFT plots in the front end with key frequencies
* Movement patterns drivers for the spots
* Sequencer and orchestrator
	* Some type of sequencer source both for short, medium and long term scheduling. Perhaps a long term scheduler is different
	* Some kind of orchestrator based on the metrics of music type
	* Some kind of scheduler for the orchestrator
* Spinning mode similar to fwd / zig zag
* All input values from the OSC sliders should be smoothed slightly via a parameter defined in click in seconds. Default should be 0.1s smoothing.
* Overall and per light brightness perception map and limits
* Can I use inheritance from parent frame in open stage control to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
* Blue/green deploy mechanism
* Trigger the next beat impulse (or all synths with the next time step)?

# Feedback
* Maybe we need softer strobes
* An alternate dumb layout URL mode
* Color wheels
* Make text bigger
* randomizer
* SQ disco struggles


# Buggy stuff
Fix 
```
# pythonosc → (addr, x, y) → args == (x, y)
# PresetManager.load → (addr, [x, y]) → args == ([x, y],)
```
Heartbeat sends all the time which it doesnt need to when it's zero
