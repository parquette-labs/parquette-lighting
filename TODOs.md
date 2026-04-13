# Real world testing needed

* DMX passthrough
* Hazer controls

# Notes/Ideas/TODOs

* Spots
	* Way to program movement patterns for the spots
	* Pan tilt to XY mapping
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
	* If I add auto binders to generators I can auto generator the osc target names (can that be done in the general case)
	* Also need a better concept of the patch param
	* Cateogry concepts for the generators
	* Can I use inheritance from parent frame in open stage control to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
	* Move the non synth params out of the generators packages
* Confirm done
	* Remove the need for wash and red to be named wash_1 wash_2 so that we can benefit from human names. It's that rn for the chan offset I think

# Feedback

* "Softer" strobes?
* An alternate simpler layout mode
* Make text bigger
* Mode randomizer

# Category information

The param groups (each builds a list of OSCParams):

  1. audio — FFT bounds, amp, threshold, LPF, BPM settings
  2. booth — booth/under fixture controls
  3. channel_levels — per-channel master levels
  4. hazer — haze machine controls
  5. non_saved — params excluded from presets
  6. plants — ceiling/plant fixture controls
  7. reds — red dimmer fixture controls
  8. spots — spot fixtures, pan/tilt, loops
  9. strobes — strobe controls
  10. washes — wash fixture RGB/RGBW controls

  Plus deps (the shared dependency dataclass) and __init__ (the builder that wires them together).

❯ what places do we have to hard code param group names?

  Searched for 1 pattern, read 1 file (ctrl+o to expand)

⏺ Category names are hardcoded in 4 places:

  1. params/__init__.py (lines 27-38) — the exposed_params dict keys
  2. preset_manager.py (lines 48-55) — the list of saveable preset categories (plus "non-saved"
  exclusion at line 155)
  3. server.py (lines 215-308) — the category= argument on each fixture
  4. generators/mixer.py (lines 62-66, 115, 122-125, 244-289) — master fader properties, impulse
  categories, channel-to-preset-group mapping, and generator routing rules
✻ Brewed for 33s


