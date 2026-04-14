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


1. Fixture creation — patching/fixtures.py

Every fixture's category= argument (lines 21-103). Covers: reds, booth, plants, spots_light, spots_position, washes, non-saved, hazer.

2. Generator creation — builder modules

Each builder creates generators with hardcoded categories:
- patching/reds.py:33, 41, 44 — reds
- patching/plants.py:18, 27, 37, 47 — plants
- patching/booth.py:18 — booth
- patching/washes.py:31, 39 — washes
- patching/spots.py:32, 41, 50, 59, 68, 77, 82, 87, 92 — spots_light, spots_position
- patching/audio.py:20, 28 — audio
- patching/strobes.py:14 — strobes

3. Builder filters — patching/washes.py:23

f.category == "washes" — uses category to filter fixtures.

4. build_params keys — each builder's return dict

- reds.py:63 → "reds"
- plants.py:77 → "plants"
- booth.py:40 → "booth"
- washes.py:64, 84 → "washes_color", "washes"
- spots.py:295 → "spots_light", "spots_position"
- audio.py:54 → "audio"
- strobes.py:24 → "strobes"
- hazer.py:17 → "hazer"
- non_saved.py:24 → "non-saved"

5. Preset manager — preset_manager.py

- Lines 48-55: hardcoded list of saveable preset categories (reds, plants, booth, spots_light, spots_position, washes, washes_color, hazer)
- Line 155: if category == "non-saved" — skip marker

6. Mixer — generators/mixer.py

- Lines 62-66: make_master_property maps a master name to its category (reds_master → "reds", etc.)
- Line 115: impulse_categories = {"washes", "non-saved"} — which categories get the impulse generator connected
- Lines 235, 242, 249, 256, 264, 273, 280: "reds" / "washes" literals for stutter channel construction
