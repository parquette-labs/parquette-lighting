# OSC Address Reference

Complete inventory of all OSC addresses used between the Python server and the Open Stage Control frontend.

## `/gen/{ClassName}/{name}/{attr}` — Generator params

Standard scalar binds via `Generator.standard_params()`, preset-saved:

| Class | Instances | Attributes |
|---|---|---|
| WaveGenerator | sin_red, sin_wash, sin_plants, sin_booth, sin_spot, sin_spot_pos_{1-4}, sq_{1-3} | amp, period, phase, duty |
| BPMGenerator | bpm_red, bpm_wash | amp, duty, bpm_mult, manual_offset, lpf_alpha |
| FFTGenerator | fft_1, fft_2 | amp, thres, lpf_alpha |
| LoopGenerator | loop_reds, loop_spot_pos_{1,2}_{x,y} | amp |
| ImpulseGenerator | impulse | amp, duty |
| NoiseGenerator | noise_1 | amp, period |

Custom per-class params (also via `standard_params()` overrides), preset-saved:

| Address | Type |
|---|---|
| `/gen/FFTGenerator/{name}/bounds` | non-scalar (4-tuple) |
| `/gen/LoopGenerator/{name}/samples` | non-scalar (list) |

Actions (dispatcher.map, not preset-saved):

| Address | Instances |
|---|---|
| `/gen/BPMGenerator/{bpm_name}/snap` | every wave that called `register_snap_to(bpm, osc)` fans in (see below) |
| `/gen/LoopGenerator/{name}/record` | loop_reds, loop_spot_pos_1 (x+y share), loop_spot_pos_2 (x+y share) |
| `/gen/LoopGenerator/{pair}/input` | loop_spot_pos_1, loop_spot_pos_2 (XY pair), loop_reds (scalar) |
| `/gen/ImpulseGenerator/impulse/punch` | trigger impulse burst |

BPM snap subscriptions:

| Snap address | Waves that snap |
|---|---|
| `/gen/BPMGenerator/bpm_red/snap` | sin_red, sin_plants, sin_booth, sin_spot, sin_spot_pos_{1-4}, sq_{1-3} |
| `/gen/BPMGenerator/bpm_wash/snap` | sin_wash |

## `/chan/{channel_name}/offset` — Mix channel offsets

One per mix channel (~40 channels), preset-saved. Registered via `MixChannel.register_offset(osc, on_change)`. Examples: `chan/left_1.dimming/offset`, `chan/spot_1.pan/offset`, `chan/reds_fwd/offset`, `chan/washes_mono/offset`.

Composite pan+tilt addresses, preset-saved. Each is a `PantiltChannel` virtual channel whose offset is a 2-vec `[pan, tilt]` that writes through to the underlying real channels; skipped from `signal_patchbay` routing.

| Address | Underlying channels |
|---|---|
| `/chan/spot_{1,2}.pantilt/offset` | `spot_{1,2}.pan`, `spot_{1,2}.tilt` |
| `/chan/spot_{1,2}.pantilt_fine/offset` | `spot_{1,2}.pan_fine`, `spot_{1,2}.tilt_fine` |

## `/chan/{category}/stutter_period` — Stutter period per category

Preset-saved. Each stutter channel in the category re-registers the same OSC address via `MixChannel.register_stutter_period(osc)`; pythonosc fans the message to all handlers.

| Address | Channels sharing it |
|---|---|
| `/chan/reds/stutter_period` | reds_fwd, reds_back, reds_zig |
| `/chan/washes/stutter_period` | washes_fwd, washes_back |

## `/fixture/{ClassName}/{name}/{attr}` — Fixture params

Preset-saved, via `Fixture.standard_params()`:

| Class | Instances | Attributes |
|---|---|---|
| YRXY200Spot | spot_1, spot_2 | color_index, pattern_index, prisim_enabled, prisim_rotation |
| RadianceHazer | hazer | target_output, target_fan, interval, duration |

RGBLight and RGBWLight do not expose per-instance `r/g/b/w_target` here — color is set via the class-level broadcasts (see below).

Class-level broadcasts (dispatcher.map, not preset-saved). Each instance of the class self-registers a handler at the same address; pythonosc fans one UI message to every instance — the frontend sends directly, no multi-send script needed.

| Address | Payload | Fans to |
|---|---|---|
| `/fixture/YRXY200Spot/reset` | trigger | spot_1, spot_2 |
| `/fixture/RGBLight/color` | 3× float (r, g, b) | wash_fl, wash_fr, wash_ml, wash_mr, wash_bl, wash_br, wash_ceil_f, wash_ceil_r |
| `/fixture/RGBWLight/w_target` | float | wash_ceil_f, wash_ceil_r |

By default RGBWLight instances also listen on `/fixture/RGBLight/color` so one UI message drives every RGB-family wash. Pass `use_rgb_color_broadcast=False` to the RGBWLight constructor to isolate an instance to `/fixture/RGBWLight/color` instead.

## `/signal_patchbay/{category}` — Signal routing matrices

Preset-saved. One per patchable category, created via `Mixer.patchbay_param(category)`.

Categories: reds, plants, booth, washes, spots_light, spots_position.

## `/{category}_master` — Category master faders

Session-saved (not preset-saved). One per category, bound via `Category.master_param`.

Categories: reds, plants, booth, washes, spots_light, spots_position, washes_color, audio, strobes, hazer, non-saved.

## `/scene/{name}` — Named lighting scenes

Actions (dispatcher.map, not preset-saved). Each `Scene` sets category masters + optional channel offsets + selects a preset group.

| Address | Preset group |
|---|---|
| `/scene/all_black` | Off |
| `/scene/house_lights` | Static |
| `/scene/class_lights` | Class |

## `/preset/…` — Preset management

| Address | Direction | Purpose |
|---|---|---|
| `/preset/save/{category}` | UI → Server | save current state as preset |
| `/preset/clear/{category}` | UI → Server | delete the selected preset |
| `/preset/selector/{category}` | bidirectional | select / echo current preset name |

## `/visualizer/…` — Data streams and enables

Server → UI (send_osc, gated by heartbeat):

| Address | Content |
|---|---|
| `/visualizer/fft` | downsampled spectrum |
| `/visualizer/fftgen_{1,2}` | current FFT generator scalar |
| `/visualizer/fftgen_{1,2}_history` | 200-sample rolling buffer |
| `/visualizer/rms_history` | RMS level history |
| `/visualizer/bpm_history` | smoothed BPM history |
| `/visualizer/raw_bpm_history` | unsmoothed BPM |
| `/visualizer/harmonic_percussive` | H/P ratio history |
| `/visualizer/business` | onset density history |
| `/visualizer/regularity` | regularity history |
| `/visualizer/synth_history` | selected synth channel history |
| `/visualizer/fixture/{name}/dimming` | per-fixture (all ~27 fixtures) |
| `/visualizer/fixture/{spot}/pantilt` | spot_1, spot_2 pan/tilt |

UI → Server (heartbeat enables):

| Address | Purpose |
|---|---|
| `/visualizer/enable_fft` | gate FFT/audio viz streams |
| `/visualizer/enable_synth` | gate synth history stream |
| `/visualizer/enable_fixture` | gate fixture dimming/pantilt streams |
| `/visualizer/synth_source` | select which channel to visualize (preset-saved) |

## `/audio_config/…` — Audio/FFT configuration

Preset-saved (OSCParam.bind on FFTManager): `bpm_energy_threshold`, `bpm_tempo_alpha`, `onset_envelope_floor`, `bpm_business_min`, `bpm_regularity_min`.

Actions (dispatcher.map): `start_audio`, `stop_audio`, `start_fft`, `stop_fft`, `port_refresh`.

Port selection: `port_name` (bidirectional), `port_name/values` (server → UI, dropdown options).

## `/dmx/…` — DMX port configuration

Preset-saved: `passthrough` (via `DMXManager.passthrough_param()`).

Actions (dispatcher.map): `port_refresh`, `port_disconnect`.

Port selection: `port_name` (bidirectional), `port_name/values` (server → UI, dropdown options).

## `/debug/…` — Debug UI frames

`fft_frame`, `audio_frame` — UIDebugFrame heartbeat containers.

## Root-level addresses

Infrastructure:

| Address | Direction | Purpose |
|---|---|---|
| `/heartbeat` | UI → Server | client keep-alive |
| `/client_count` | Server → UI | connected client count |
| `/reload` | UI → Server | re-sync all presets to frontend |
| `/enable_save` | bidirectional | toggle preset save/clear |

## Frontend-only multi-sends

These widgets have `address: ""` and use `onValue` scripts to fan out to multiple backend addresses.

| Widget | Sends to |
|---|---|
