# Pre show todos

* Adjust levels with real input

# Untested
* DMX passthrough
* Real hazer

# Notes/Ideas/TODOs

* Something is wrong with BPM again? Seems related to the update freq (I set the interval back to 1s)
* Update the BPM much less often for smoothing?
* Transition from spot off doesnt' do the fade right due to the jump in levels
* <s>Save state across reboot</s>
* Retry XY mapping work
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
* Trigger the next beat impulse (or all synths with the next time step)?
* Viz should connect to an out channel

# Feedback
* Maybe we need softer strobes
* An alternate dumb layout URL mode
* Color wheels
* Make text bigger
* Randomizer
* SQ disco struggles

