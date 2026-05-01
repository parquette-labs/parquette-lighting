# OSC Address Reference

Complete inventory of OSC addresses between the Python server and the Open Stage Control frontend. Unless noted, UI → Server addresses are bidirectional (server syncs current value on preset load / client reconnect).

## `/gen/{ClassName}/{name}/{attr}` — Generator params

Standard scalar binds via `Generator.standard_params()`, preset-saved. The attribute list comes from each class's `STANDARD_ATTRS`.

| Class | Instances | Attributes |
|---|---|---|
| WaveGenerator | sin_red, sin_wash, sqr_wash, sin_plants, sin_booth, sin_spot, sqr_spot, sin_spot_pos_{1-4}, sin_chand_{1-3}, sq_{1-3} | amp, period, phase, duty |
| BPMGenerator | bpm_red, bpm_wash | amp, duty, bpm_mult, manual_phase, lpf_alpha |
| FFTGenerator | fft_1, fft_2 | amp, thres |
| LoopGenerator | loop_reds, loop_spot_pos_{1,2}_{x,y} | amp |
| ImpulseGenerator | impulse | amp, duty |

Custom per-class params (via `standard_params()` overrides), preset-saved:

| Address | Type |
|---|---|
| `/gen/FFTGenerator/{name}/bounds` | non-scalar (4-tuple — low, 0, high, 0) |
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
| `/gen/BPMGenerator/bpm_red/snap` | sin_red, sin_plants, sin_booth, sin_spot, sqr_spot, sin_spot_pos_{1-4}, sin_chand_{1-3}, sq_{1-3} |
| `/gen/BPMGenerator/bpm_wash/snap` | sin_wash, sqr_wash |

`NoiseGenerator` exists in the codebase (`generators/noise_generator.py`, `STANDARD_ATTRS = ["amp", "period"]`) but has no instances and registers no addresses.

## `/chan/{fixture}/{attr}/offset` — Mix channel offsets

One per real mix channel, preset-saved. Registered via `MixChannel.register_offset(osc, on_change)`. Channel names use `/` as the fixture/attribute separator (not `.`) so `@{chan/…/offset}` references work in Open Stage Control — OSC parses dots in `@{id}` as JS property access.

`ChannelLevelsBuilder` walks `mixer.mix_channels` and binds an offset OSCParam for every channel except virtual ones (`PantiltChannel`); the spot builder registers the virtual pantilt offset itself.

Real channels:
- Per-LightFixture dimming: `chan/{fixture}/dimming/offset` for `left_{1-4}`, `right_{1-4}`, `front_{1,2}`, `under_{1,2}`, `ceil_{1-3}`, `chand_{1-3}`, `tung_spot`, `pin_1`, `sodium`
- Per-RGB(W) wash dimming: `chan/{wash}/dimming/offset` for `wash_fl`, `wash_fr`, `wash_ml`, `wash_mr`, `wash_bl`, `wash_br`, `wash_ceil_f`, `wash_ceil_r`
- Per-YRXY200Spot: `chan/spot_{1,2}/dimming/offset`, `chan/spot_{1,2}/x_coord/offset`, `chan/spot_{1,2}/y_coord/offset` (x/y are mapping-space 16-bit values; `post_map_output` converts to real pan/tilt at DMX-write time)
- Hazer: `chan/hazer/output/offset`, `chan/hazer/fan/offset`
- Mono / stutter composite channels (no slash inside the channel name): `chan/reds_mono/offset`, `chan/reds_fwd/offset`, `chan/reds_back/offset`, `chan/reds_zig/offset`, `chan/washes_mono/offset`, `chan/washes_fwd/offset`, `chan/washes_back/offset`

Virtual pantilt addresses, preset-saved — `PantiltChannel` channels whose offset is a 2-vec `[x_coord, y_coord]` that writes through to the underlying `x_coord`/`y_coord` mix channels; skipped from `signal_patchbay` routing because they are pure OSC facades.

| Address | Underlying channels |
|---|---|
| `/chan/spot_{1,2}/pantilt/offset` | `spot_{1,2}/x_coord`, `spot_{1,2}/y_coord` |

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

`RGBLight`, `RGBWLight`, and `PinSpot` expose no per-instance attrs — color is set via the class-level broadcasts below.

## `/fixture/{ClassName}/{action}` — Class-level fixture broadcasts

Each instance self-registers a handler at the same address; pythonosc fans one UI message to every instance of the class — the frontend sends directly, no multi-send script needed. The color/w_target binds are preset-saved (registered as OSCParams via `color_param()` / `w_target_param()`); `reset` is a dispatcher action.

| Address | Payload | Fans to |
|---|---|---|
| `/fixture/YRXY200Spot/reset` | trigger | spot_1, spot_2 |
| `/fixture/RGBLight/color` | 3× float (r, g, b) | wash_fl, wash_fr, wash_ml, wash_mr, wash_bl, wash_br, wash_ceil_f, wash_ceil_r |
| `/fixture/RGBWLight/w_target` | float | wash_ceil_f, wash_ceil_r |
| `/fixture/PinSpot/color` | 3× float (r, g, b) | pin_1 |
| `/fixture/PinSpot/w_target` | float | pin_1 |

By default `RGBWLight` instances also listen on `/fixture/RGBLight/color` so one UI message drives every RGB-family wash. Pass `use_rgb_color_broadcast=False` to the constructor to isolate an instance to `/fixture/RGBWLight/color` instead.

## `/signal_patchbay/{category}` — Signal routing matrices

Preset-saved. One per patchable category, created via `Mixer.patchbay_param(category)`. Virtual channels (PantiltChannel) are excluded from routing.

Categories: reds, plants, booth, washes, spots_light, spots_position, chandelier.

## `/{category}_master` — Category master faders

Session-saved (not preset-saved). Created via `Category.master_param` during `Categories.__init__`.

Categories: reds, plants, booth, spots_light, washes, spots_position, washes_color, audio, strobes, hazer, chandelier, non-saved.

## `/scene/{name}` — Named lighting scenes

Triggered via `dispatcher.map("/scene/*", ...)` — the wildcard handler looks up `name` in the scene dict and calls `scene.activate()` (sets category masters, optional channel offsets, optionally disables DMX passthrough, applies a preset group).

The `name` segment in the address is the scene's display name verbatim (including spaces). Built-in scenes registered in `server.py`:

| Address | Preset group | Notes |
|---|---|---|
| `/scene/All Black` | Off | zeroes every master, sodium offset → 0 |
| `/scene/House Lights` | Static | masters up, sodium → 255, disables DMX passthrough |
| `/scene/Class Lights` | Class | partial masters, disables DMX passthrough |

User-created scenes (loaded from `scenes.pickle`) appear at the same `/scene/{name}` pattern. The scene management actions (dispatcher.map):

| Address | Direction | Purpose |
|---|---|---|
| `/scene/create` | UI → Server | capture current state as a scene; payload is the scene name string |
| `/scene/save_current` | UI → Server | overwrite the currently selected scene |
| `/scene/clear_current` | UI → Server | delete the currently selected scene |
| `/scene_selector` | bidirectional | echo / select the active scene name |
| `/scene_selector/values` | Server → UI | scene-name → name dict for the dropdown |

## `/preset/…` — Preset management

| Address | Direction | Purpose |
|---|---|---|
| `/preset/save/{category}` | UI → Server | save current state as preset |
| `/preset/clear/{category}` | UI → Server | delete the selected preset |
| `/preset/selector/{category}` | bidirectional | select / echo current preset name |
| `/preset/reload` | UI → Server | re-sync every preset-tracked param to the frontend (also resyncs the scene dropdown) |
| `/preset/restore_defaults` | UI → Server | overwrite the active pickle with `default-params.pickle` and reload (gated by `enable_save`) |

## `/coord_system` — Active coord system selector

Bidirectional. Bound by `CoordSystemState` to the active `CoordSystem` name (e.g. `"pantilt"`, `"latlon"`). Persists in the session pickle; intentionally not preset-saved (it's a UI / shell preference, decoupled from preset state). Setting it triggers `rebind_coords(old, new)` on every registered fixture so spots stay still across the toggle.

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
| `/visualizer/fixture/{name}/dimming` | per-LightFixture |
| `/visualizer/fixture/{spot}/pantilt` | spot_1, spot_2 — `[pan, tilt]` real values |

UI → Server:

| Address | Purpose |
|---|---|
| `/visualizer/enable_fft_spectrum` | heartbeat to gate FFTManager's spectrum + audio-analysis streams (`/visualizer/fft`, `/visualizer/fftgen_{1,2}`, `rms/bpm/harmonic_percussive/business/regularity` histories) |
| `/visualizer/enable_fft_gen_timeseries` | heartbeat to gate Mixer's `/visualizer/fftgen_{1,2}_history` 200-sample buffers |
| `/visualizer/enable_synth` | heartbeat to gate synth history stream |
| `/visualizer/enable_fixture` | heartbeat to gate fixture dimming/pantilt streams |
| `/visualizer/synth_source` | select which channel to visualize (non-saved category) |

The four `enable_*` heartbeats are driven by the top-level tab switcher's `onValue` script, which sends `1` for the matching tab index and `0` otherwise. The server only treats `1` as a heartbeat (extends the gate by ~2s); `0` messages are ignored so a second UI client on a different tab can't yank the gate closed.

## `/audio_config/…` — Audio + FFT configuration

Preset-saved (`OSCParam.bind` on FFTManager via `config_params()`):

`bpm_energy_threshold`, `bpm_tempo_alpha`, `bpm_phase_alpha`, `onset_envelope_floor`, `bpm_business_min`, `bpm_regularity_min`, `bpm_outlier_window`, `bpm_publish_interval`.

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

## Frontend-only fan-outs

A handful of widgets in `open-stage-control/layout-config.json` send to additional addresses via `onValue` scripts — not part of the server's address scheme, just UI ergonomics.

| Widget / control | Sends to |
|---|---|
| Top-level tab switcher | `/visualizer/enable_fft_spectrum`, `/visualizer/enable_fft_gen_timeseries`, `/visualizer/enable_synth`, `/visualizer/enable_fixture` (one address per active-tab index) |
| Scene dropdown | `/scene/{value}` whenever a scene name is picked |
| Scene name buttons | `/scene/create`, `/scene/save_current`, `/scene/clear_current` |
| Spot pantilt nudge buttons (per spot, 4 directions) | `/chan/spot_{1,2}/pantilt/offset` (read-modify-write by `spot_{1,2}_nudge_step`) |
| Loop XY canvas controls (per spot) | local `updateCanvas` / `clearDragPath` only |
| FFT filter envelope widgets | local `fft_filter` variable used by other widgets |
