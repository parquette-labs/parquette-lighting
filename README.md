# Parquette Lighting 🪩🪴🕺🪩🕺🪴🪩

# Basic Setup on Mac

* Install [brew](https://brew.sh/)
* `brew install pyenv` then [setup pyenv shims](https://github.com/pyenv/pyenv?tab=readme-ov-file#macos)
* `brew install portaudio`
* Install python 3.9.9 + (mac mini running 3.13.3), e.g. `pyenv install 3.13.3`
* Create a pyenv or set global, e.g. `pyenv virtualenv parquette 3.13.3` and `pyenv local parquette` in the repo
* `pip install poetry` in the pyenv
* in python/parquette-lights/
	* `poetry sync`
	* `poetry run server`

# Launchd setup

* in `launchd/`
	* `./install` will install and offer to launch the launchctl service
	* check status with `launchctl list ca.parquette.lighting.server` `launchctl list ca.parquette.lighting.openstagecontrol` and check for `LastExitStatus = 0`
	* should auto launch on machine boot

# Running the system

* Wiring
	* Connect DMX Entec Pro to mac mini via USB
	* Connect USB audio interface (or any audio input your computer detects), connect to line out from the DJ booth. There is currently a small amazon USB audio dongle that takes headphone jack input and an XLR to headphone adapter attached
	* Connect DMX Entec Pro via DMX cable (need a 5 to 3 pin adapter) to the dimmer pack above the washroom
	* TODO: Notes on the artnet setup alternative are missing
* Software
	* Boot computer, current mac mini is set to auto boot when it has power
	* Connect via screen share
		* Go to Finder on a mac
		* Press Cmd+K
		* enter `vnc://pq@parquette-house-mm.local` (note only accessible on the internal WiFi?)
		* Use password for wifi for the screen share
		* Login to the machine with same password
	* Open "Open Stage Control" from Applications and hit the play button
	* Open terminal
		* `cd ~/parquette/parquette-lighting/python/parquette-lights`
		* `poetry run server`
		* TODO notes on auto connect for DMX are missing
* Config
	* Go to [http://192.168.1.245:8080](http://192.168.1.245:8080) in your browser (note only accessible on the internal WiFi)
	* Go into "FFT and DMX Setup"
	* DMX
		* Press "Refresh DMX ports"
		* Select DMX port from drop down (if none you have a wiring problem with your Entec probably?)
		* Selecting an item from the menu connects to it
		* You should be able to control lights, they will snap to the current settings
	* Audio
		* Press "Refresh Audio ports"
		* Select audio port from drop down
		* Wait 4-5s for backend to catchup configuring audio port
		* Press "Start Audio"
		* Wait 1-2s
		* Press "Start FFT"
		* You should see audio signal coming in to the FFT visualizer

# Repo information

* `/open-stage-control` contains the configuration for the open stage control front end, the `layout-config.json` contains the front end design, the other files are the server and UI initial state
* `/launchd` contains the launchd scripts and install
* `/python/parquette-lights` contains the python server
	* `/python/parquette-lights/params.pickle` contains the presets, it is auto updated when you adjust the presets in the front end (by clicking save or clear preset). You of course have to save and commit those changes for them to persist

## Notes/Ideas/TODOs
* Some kind of visualizer to test in realtime without lights: create an additional target in the mixer that doesn't route to any DMX, instead it send the value out as OSC a colored square in the front end for debugging. This target sink should be available in all the patchbays.
* Presets, automations and controls
	* Interpolate between presets when you switch over
	* All input values from the OSC sliders should be smoothed slightly via a parameter defined in click in seconds. Default should be 0.1s smoothing.
* Spots
	* Create a mapping between pan tilt and XY mapping to make the controls more intutive. This is the moving head spots YUERLT YRYX200WJLSMD with 540 degrees of pan and 200 degrees of tilt. The extra pan range should be used to minimze distance travelled, otherwise moving heads should prefer to be in the center of their range of motion.
	* Auto fade in-out for color changes with a click option to enable and disable this. The moving head fixtures should quickly fade out then switch colors in the color wheel then fade back in.The click option should be a number of seconds for the fade out / fade in and if the value is negative this feature should be disabled. 
* Math problems
	* The FWD/BACK memory slice needs the memory slices to be log spaced or similar, e.g. more slices at the short time scale and fewer slices at the long timescale. This might be impossible if we're only computing every 10ms or so
	* Adjust how master level works. 
	* Add floor / ceil / scaling instead of just offest and mult for chans
	* Prevent negative values?
	* Per chanel master multipler sliders

	* Bug with adjusting the period of osciallators causing jump
* Bugs
	* Preset overwritting may have bugs
	* Improve threading issues, can we run faster
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
	* !Optimize compute by idyling FFT and BPM when there is no audio and/or no interaction for multiple days
	* Use inheritance from parent frame to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
	* Better parent class for Spot with no repeated boiler plate
	* Some type of sequencer source
	* Auto detection for low/high intensity of music that can trigger mode changes or similar
	* Blue/green deploy mechanism
	* Spinning mode
	* Switch to dual spectrograms for harmonic and percussive
	* Wave generators should be able to switch shapes without rewiring in the patchbay? Or general rethink of the patchbay
	* Can I move the mapping definitions for output mix into the front end fully?
	* Auto load channel and generator names from the front end or scrupting to sync between front and backend
	* It would be cool to have some smoothing or softening for hits, e.g. BPM or FFT, so it feels more organic and less sharp. In particular for example the BPM blip wash mode could be softer
