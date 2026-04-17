# Real world testing needed

* DMX passthrough
* Hazer controls

# Notes/Ideas/TODOs

* Spots
	* [partial] Pan tilt to XY mapping
	* [mvp] Way to program movement patterns for the spots
	* I need a way to change the loop intensity without moving it's average xy position
* Other lights
	* sq1, sq2, sq3, need to have separate period controls or some nicer way to make them chaotic
* Orchestration
	* Sequencer and orchestrator for short to long term scheduling. It could schedule specific effects or sets of effects to be controlled by the orgestrator
	* Some randomization methods inthis
* FFT/BPM
	* BPM offset is still flakey, need to consider how to design a more coherent / human friendly mode
	* The BPM confidence is kinda bouncy, I want it quick to come on but not too bouncy
	* Annotate FFT plots in the front end with key frequencies
* Effects
	* Spinning mode where lights rotate around the room
	* Some type of spatial mapping or better approach that is more generic for the spatial movements
* General perceptual improvements
	* Overall and per light brightness and color mapping and limits
* Hardware
	* Debug non SHED fixtures
* Code structure
	* Fix naming conflicts with "offset"
	* The chanel visualizer doesn't work on some channels, also some ui elements still say . for / 
	* Can I use inheritance from parent frame in open stage control to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
	* Can the backend keep the front end in sync for addresses and/or ui elements
* Confirm done
	* Remove the need for wash and red to be named wash_1 wash_2 so that we can benefit from human names. It's that rn for the chan offset I think

# Feedback

* "Softer" strobes?
* An alternate simpler layout mode
* Make text bigger
* Mode randomizer
