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
	* Loops generator input doesn't need to be saved
	* rename standard param
	* Fix naming conflicts with "offset"
	* If I add auto binders to generators I can auto generator the osc target names (can that be done in the general case)
	* Also need a better concept of the patch param
	* Can I use inheritance from parent frame in open stage control to make more reusabe stage control blocks, e.g. parent called spot_1 which is used in the child address names
	* Move the non synth params out of the generators packages
	* /fixture/YRXY200Spot/spot_{1,2}/reset should not contrain spot12, same with wash_color and was_w
	* Build "/chan/{}/offset".format(ch.name)" in chan
	* into DMX OSCParam.bind(osc, "/dmx/passthrough", self.dmx, "passthrough")
	* Can the backend keep the front end in sync for addresses and/or ui elements
* Confirm done
	* Remove the need for wash and red to be named wash_1 wash_2 so that we can benefit from human names. It's that rn for the chan offset I think

# Feedback

* "Softer" strobes?
* An alternate simpler layout mode
* Make text bigger
* Mode randomizer

# OSC Addresses

⏺ Here's the full catalog of OSC addresses, organized by source file:

  dmx.py

  - /dmx_port_refresh — trigger a refresh of DMX ports (line 109, incoming)
  - /dmx_port_disconnect — disconnect current port (line 112, incoming)
  - /dmx_port_name — select DMX port by name (line 116, incoming; outgoing at 142, 231)
  - /dmx_port_name/values — available DMX port options (line 130, outgoing)

  audio_analysis/audio.py

  - /audio_debug_frame — debug frame output (line 36, UIDebugFrame)
  - /audio_port_refresh — refresh audio ports (line 40, incoming)
  - /audio_port_name — select audio port (line 43 incoming; 94, 152 outgoing)
  - /audio_port_name/values — available audio ports (line 62, outgoing)
  - /start_audio — start audio capture (line 45, incoming)
  - /stop_audio — stop audio capture (line 46, incoming)

  audio_analysis/fft.py

  - /fft_debug_frame — debug frame output (line 97, UIDebugFrame)
  - /start_fft — start FFT thread (line 102, incoming)
  - /stop_fft — stop FFT thread (line 103, incoming)
  - /set_fft_viz — enable FFT viz heartbeat (line 105, incoming — also line 347 in server.py)
  - /fft_viz — FFT spectrum data (lines 485, 489, outgoing)
  - /fftgen_1_viz, /fftgen_2_viz — FFT generator output values (lines 498, 499, outgoing)
  - /rms_history_viz — RMS history (line 501, outgoing)
  - /bpm_history_viz — BPM history (line 502, outgoing)
  - /raw_bpm_history_viz — raw BPM history (line 504, outgoing)
  - /harmonic_percussive_viz — harmonic/percussive split (line 507, outgoing)
  - /business_viz — business metric history (line 510, outgoing)
  - /regularity_viz — regularity metric history (line 511, outgoing)
  - /audio_nyquist — sends Nyquist when audio rate is known

  category.py

  - /{category}_master — per-category master fader, bound to Category.master (line 27). Generates: /reds_master, /plants_master, /booth_master, /spots_light_master, /washes_master, /spots_position_master,
  /washes_color_master, /audio_master, /strobes_master, /hazer_master, /non-saved_master

  fixtures/basics.py

  - /visualizer/{fixture_name} — fixture dimming value for UI (line 131, outgoing)

  fixtures/spotlights.py

  - /reset_spots — reset all spots (line 52, incoming; each Spot self-registers)
  - /visualizer/{fixture_name}/pantilt — spot pan/tilt values (line 477, outgoing)

  generators/mixer.py

  - /synth_visualizer_history — synth visualizer channel history (line 404, outgoing)
  - /fftgen_1_history, /fftgen_2_history — FFT gen history buffers (lines 407, 408, outgoing)

  util/client_tracker.py

  - /heartbeat — client heartbeat (default arg, line 20)
  - /client_count — broadcast client count (default arg, line 21)

  preset_manager.py

  - /save_preset/* — save preset by category (line 36, incoming)
  - /clear_preset/* — clear preset (line 39, incoming)
  - /preset_selector/* — select preset by category (line 42, incoming; line 198 outgoing)
  - /enable_save — save-mode toggle (line 200, outgoing; line 304 in server.py incoming)

  server.py

  - /reload — resync presets (line 302, incoming)
  - /set_fft_viz, /set_synth_visualizer, /set_fixture_visualizer — visualizer gate heartbeats (lines 347, 350, 354, incoming)
  - /all_black, /house_lights, /class — scene shortcuts (lines 357–359, incoming)

  patching/strobes.py

  - /impulse_punch — trigger impulse (line 19, incoming)
  - /impulse_amp, /impulse_duty

  patching/audio.py

  - /fft1_amp, /fft2_amp
  - /fft_lpf_alpha, /fft_threshold_1, /fft_threshold_2
  - /fft_bounds_1, /fft_bounds_2
  - /bpm_energy_threshold, /bpm_tempo_alpha, /onset_envelope_floor, /bpm_business_min, /bpm_regularity_min

  patching/reds.py

  - /snap_sin_red_to_bpm, /sin_red_period
  - /loop_reds_record, /loop_reds_input, /loop_reds_amp, /loop_reds_samples
  - /signal_patchbay/reds
  - /reds_stutter_period
  - /sin_red_amp
  - /bpm_red_mult, /bpm_red_duty, /bpm_red_lpf_alpha, /bpm_red_amp, /bpm_red_manual_offset

  patching/plants.py

  - /snap_sin_plants_to_bpm, /sin_plants_period, /sin_plants_amp
  - /snap_sq_to_bpm, /sq_amp, /sq_period
  - /signal_patchbay/plants

  patching/booth.py

  - /snap_sin_booth_to_bpm, /sin_booth_period, /sin_booth_amp
  - /signal_patchbay/booth

  patching/washes.py

  - /snap_sin_wash_to_bpm, /period_wash, /amp_wash
  - /bpm_wash_amp, /bpm_wash_duty, /bpm_wash_lpf_alpha, /bpm_wash_mult, /bpm_wash_manual_offset
  - /signal_patchbay/washes, /washes_stutter_period
  - /wash_w, /wash_color

  patching/spots.py

  - /snap_sin_spot_to_bpm, /sin_spot_period, /sin_spot_amp
  - /snap_sin_spot_pos_to_bpm
  - /sin_spot_pos_{1-4}_amp, /sin_spot_pos_{1-4}_period
  - /loop_spot_pos_{1,2}_record, /loop_spot_pos_{1,2}_input
  - /loop_spot_pos_{1,2}_x_amp, /loop_spot_pos_{1,2}_y_amp
  - /{fixture_name}_samples (loop sample data per axis)
  - /signal_patchbay/spots_light, /signal_patchbay/spots_position
  - /spot_color_{1,2}, /spot_pattern_{1,2}, /spot_prisim_{1,2}, /spot_prisim_rotation_{1,2}
  - /{fixture_name}_pantilt_offset, /{fixture_name}_pantilt_fine_offset

  patching/hazer.py

  - /hazer_intensity, /hazer_fan, /hazer_interval, /hazer_duration

  patching/non_saved.py

  - /dmx_passthrough
  - /synth_visualizer_source

  patching/channel_levels.py

  - /mix_chan_offset/{channel_name} — per-channel offset trim (line 22)
