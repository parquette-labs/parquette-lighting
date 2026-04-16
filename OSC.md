# OSC Address Reference

Complete inventory of OSC addresses between the Python server and the Open Stage Control frontend. Unless noted, UI → Server addresses are bidirectional (server syncs current value on preset load / client reconnect).

## `/gen/{ClassName}/{name}/{attr}` — Generator params

Standard scalar binds via `Generator.standard_params()`, preset-saved:

| Class | Instances | Attributes |
|---|---|---|
| WaveGenerator | sin_red, sin_wash, sin_plants, sin_booth, sin_spot, sin_spot_pos_{1-4}, sq_{1-3} | amp, period, phase, duty |
| BPMGenerator | bpm_red, bpm_wash | amp, duty, bpm_mult, manual_offset, lpf_alpha |
| FFTGenerator | fft_1, fft_2 | amp, thres |
| LoopGenerator | loop_reds, loop_spot_pos_{1,2}_{x,y} | amp |
| ImpulseGenerator | impulse | amp, duty |

Custom per-class params (via `standard_params()` overrides), preset-saved:

| Address | Type |
|---|---|
| `/gen/FFTGenerator/{name}/bounds` | non-scalar (4-tuple) |
| `/gen/LoopGenerator/{name}/samples` | non-scalar (list) |

Class-level binds, preset-saved. Every instance registers at the same address; pythonosc fans one UI message to every instance so they stay in sync.

| Address | Fans to |
|---|---|
| `/gen/FFTGenerator/lpf_alpha` | fft_1, fft_2 |

Actions (dispatcher.map, not preset-saved):

| Address | Effect |
|---|---|
| `/gen/BPMGenerator/{bpm_name}/snap` | every wave subscribed to this BPM snaps its period — see subscription table below |
| `/gen/LoopGenerator/{name or record_group}/record` | start/stop recording; paired x/y loops share a `record_group` so one toggle drives both |
| `/gen/LoopGenerator/{name or pair}/input` | live value input; records sample during capture |
| `/gen/ImpulseGenerator/impulse/punch` | fire a one-shot impulse |

Addresses in use for the action families above:

| Family | Concrete addresses |
|---|---|
| record | `/gen/LoopGenerator/loop_reds/record`, `/gen/LoopGenerator/loop_spot_pos_1/record`, `/gen/LoopGenerator/loop_spot_pos_2/record` |
| input | `/gen/LoopGenerator/loop_reds/input` (scalar), `/gen/LoopGenerator/loop_spot_pos_1/input` (XY pair), `/gen/LoopGenerator/loop_spot_pos_2/input` (XY pair) |

BPM snap subscriptions (every wave that called `WaveGenerator.register_snap_to(bpm, osc)` registers a handler at the BPM's snap address; pythonosc fans each trigger to all handlers):

| Snap address | Waves that snap |
|---|---|
| `/gen/BPMGenerator/bpm_red/snap` | sin_red, sin_plants, sin_booth, sin_spot, sin_spot_pos_{1-4}, sq_{1-3} |
| `/gen/BPMGenerator/bpm_wash/snap` | sin_wash |

## `/chan/{channel_name}/offset` — Mix channel offsets

One per mix channel, preset-saved. Registered via `MixChannel.register_offset(osc, on_change)`. Real channels: per-fixture `{fixture}.dimming` (~16), per-spot `spot_{1,2}.{pan,pan_fine,tilt,tilt_fine}`, plus mono/stutter composites `reds_mono`, `reds_fwd`, `reds_back`, `reds_zig`, `washes_mono`, `washes_fwd`, `washes_back`.

Composite pan+tilt addresses, preset-saved — `PantiltChannel` virtual channels whose offset is a 2-vec `[pan, tilt]` that writes through to the real channels; skipped from `signal_patchbay` routing.

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

`RGBLight` and `RGBWLight` expose no per-instance attrs — color is set via the class-level broadcasts below.

## `/fixture/{ClassName}/{action}` — Class-level fixture broadcasts

Actions (dispatcher.map, not preset-saved). Each instance self-registers a handler at the same address; pythonosc fans one UI message to every instance of the class — the frontend sends directly, no multi-send script needed.

| Address | Payload | Fans to |
|---|---|---|
| `/fixture/YRXY200Spot/reset` | trigger | spot_1, spot_2 |
| `/fixture/RGBLight/color` | 3× float (r, g, b) | wash_fl, wash_fr, wash_ml, wash_mr, wash_bl, wash_br, wash_ceil_f, wash_ceil_r |
| `/fixture/RGBWLight/w_target` | float | wash_ceil_f, wash_ceil_r |

By default `RGBWLight` instances also listen on `/fixture/RGBLight/color` so one UI message drives every RGB-family wash. Pass `use_rgb_color_broadcast=False` to the constructor to isolate an instance to `/fixture/RGBWLight/color` instead.

## `/signal_patchbay/{category}` — Signal routing matrices

Preset-saved. One per patchable category, created via `Mixer.patchbay_param(category)`. Virtual channels (PantiltChannel) are excluded from routing.

Categories: reds, plants, booth, washes, spots_light, spots_position.

## `/{category}_master` — Category master faders

Session-saved (not preset-saved). Created via `Category.master_param` during `Categories.__init__`.

Categories: reds, plants, booth, washes, spots_light, spots_position, washes_color, audio, strobes, hazer, non-saved.

## `/scene/{name}` — Named lighting scenes

Actions (dispatcher.map, not preset-saved). Each `Scene` sets category masters + optional channel offsets + selects a preset group.

| Address | Preset group | Notes |
|---|---|---|
| `/scene/all_black` | Off | zeroes every master, sodium offset → 0 |
| `/scene/house_lights` | Static | masters up, sodium → 255, disables DMX passthrough |
| `/scene/class_lights` | Class | partial masters, disables DMX passthrough |

## `/preset/…` — Preset management

| Address | Direction | Purpose |
|---|---|---|
| `/preset/save/{category}` | UI → Server | save current state as preset |
| `/preset/clear/{category}` | UI → Server | delete the selected preset |
| `/preset/selector/{category}` | bidirectional | select / echo current preset name |
| `/preset/reload` | UI → Server | re-sync every preset-tracked param to the frontend |

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
| `/visualizer/fixture/{name}/dimming` | per-LightFixture (26 instances) |
| `/visualizer/fixture/{spot}/pantilt` | spot_1, spot_2 pan/tilt |

UI → Server:

| Address | Purpose |
|---|---|
| `/visualizer/enable_fft_spectrum` | heartbeat to gate FFTManager's spectrum + audio-analysis streams (`/visualizer/fft`, `/visualizer/fftgen_{1,2}`, `rms/bpm/harmonic_percussive/business/regularity` histories) |
| `/visualizer/enable_fft_gen_timeseries` | heartbeat to gate Mixer's `/visualizer/fftgen_{1,2}_history` 200-sample buffers |
| `/visualizer/enable_synth` | heartbeat to gate synth history stream |
| `/visualizer/enable_fixture` | heartbeat to gate fixture dimming/pantilt streams |
| `/visualizer/synth_source` | select which channel to visualize (non-saved category) |

## `/audio_config/…` — Audio/FFT configuration

Preset-saved (`OSCParam.bind` on FFTManager): `bpm_energy_threshold`, `bpm_tempo_alpha`, `onset_envelope_floor`, `bpm_business_min`, `bpm_regularity_min`.

Actions (dispatcher.map): `start_audio`, `stop_audio`, `start_fft`, `stop_fft`, `port_refresh`.

Port selection (non-preset, bidirectional): `port_name`; `port_name/values` carries the dropdown options server → UI.

## `/dmx/…` — DMX port configuration

`passthrough` is bound via `DMXManager.passthrough_param()` — lives in the non-saved category, so it is not preset-saved.

Actions (dispatcher.map): `port_refresh`, `port_disconnect`.

Port selection (bidirectional): `port_name`; `port_name/values` carries the dropdown options server → UI.

## `/debug/…` — Debug UI frames

`fft_frame`, `audio_frame` — `UIDebugFrame` heartbeat containers (server → UI with debug metrics).

## Root-level addresses

| Address | Direction | Purpose |
|---|---|---|
| `/heartbeat` | UI → Server | client keep-alive (sent every 2s from `onCreate`) |
| `/client_count` | Server → UI | connected client count |
| `/enable_save` | bidirectional | toggle preset save/clear UI |

## Frontend-only ganged controls

A few widgets fan a single value to sibling addresses via `onValue` scripts — not an OSC addressing scheme, just UI ergonomics.

| Widget | Sends to |
|---|---|
| `gen/WaveGenerator/sq_1/amp` | also `/gen/WaveGenerator/sq_{2,3}/amp` |
| `gen/WaveGenerator/sq_1/period` | also `/gen/WaveGenerator/sq_{2,3}/period` |
