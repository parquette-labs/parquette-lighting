# Real world testing needed

* DMX passthrough
* Hazer controls

# Notes/Ideas/TODOs

* Preset for harm reduction, vibes but light
* Spots
	* XY mapping doesn't really work well
* Other lights
	* Are other bpms affected by the long time stamps
	* Better use of 20ms time slice (can it be smaller), stobe implementation in particular needs to slice around that
* Orchestration
	* !Scenes
	* !popups to create and manage presets / scenes
	* Sequencer and orchestrator for short to long term scheduling. It could schedule specific effects or sets of effects to be controlled by the orgestrator
	* Some randomization methods in this
	* The loop gets stuck (maybe because of tick?)
* FFT/BPM
	* Shelf / change of tempo for the clusters doesn't work
	* Still small skips
	* When we have 2 clusters very close in size it will flip flop
	* Guarantee that a phase change can't re tigger withing the same period
	* FFT low end is terrible, likely something related to mels, maybe I should drop that
	* Dynamic range for at least FFT needs to clip (maybe all signal outputs?)
	* BPM offset is still flakey, need to consider how to design a more coherent / human friendly mode
	* The BPM confidence is kinda bouncy, I want it quick to come on but not too bouncy
	* Annotate FFT plots in the front end with key frequencies
* Effects
	* Spinning mode where lights rotate around the room
	* Some type of spatial mapping or better approach that is more generic for the spatial movements
* General perceptual improvements
	* Overall and per light brightness
	* Better color mapping for washes
	* Can we have it calculate the theoretical range for a setup and have masters squish us into that range?
* Hardware
	* Debug non SHED fixtures
* Code structure
	* Can I use inheritance from parent frame in open stage control to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
	* Can the backend keep the front end in sync for addresses and/or ui elements

# Feedback

* "Softer" strobes?
* An alternate simpler layout mode
* Make text bigger
* Mode randomizer
