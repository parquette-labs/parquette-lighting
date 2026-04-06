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
	* You can also connect your DMX to an art net node and configure it via `--art-net-ip` and `--boot-art-net`
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
		* You may want to auto connect to your DMX with `--entec-auto "/dev/tty.usbserial-EN264168"` or similar
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
