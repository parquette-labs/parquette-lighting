# OSC Address Reference

Complete inventory of OSC addresses between the Python server and the Open Stage Control frontend.

## Conventions

These four terms recur throughout. Each section below assumes them; only deviations are called out inline.

- **Bind** — `OSCParam.bind(...)`. Bidirectional: UI sets → server applies; server pushes the current value back on preset load and client reconnect.
- **Action** — `dispatcher.map(...)`. UI → Server only, one-shot trigger, never preset-saved.
- **Fan-out** — many handlers register at the same address; pythonosc dispatches each incoming message to every handler. Used by class-level fixture broadcasts, per-category stutter, and BPM snap.
- **Persistence tier** — four tiers, named explicitly per section:
  - *preset-saved* → `params.pickle` (per category, swapped via `/preset/selector/...`)
  - *session-saved* → `session.pickle` (master faders, sodium offset, active coord system, current preset selection)
  - *scene-saved* → `scenes.pickle` (user-created scenes — name, masters dict, optional per-category preset overrides; built-in scenes are code, not persisted)
  - *non-persistent* → RAM only

Tables omit a Direction column when every row follows its section's default (binds bidirectional, actions UI → Server). Server → UI streams call out the direction in the section header.

The "Port selection" pattern used by audio and DMX is the same in both: `port_name` is a bidirectional bind for the active port, and the server pushes the dropdown options to `port_name/values`.

## `/gen/{ClassName}/{name}/{attr}` — Generator params

Standard scalar binds, preset-saved. Built by `Generator.standard_params()` from each subclass's `STANDARD_ATTRS`.

| Class | Instances | Attributes |
|---|---|---|
| WaveGenerator | see grouping below | amp, period, phase, duty |
| BPMGenerator | bpm_red, bpm_wash | amp, duty, bpm_mult, manual_phase, lpf_alpha |
| FFTGenerator | fft_1, fft_2 | amp, thres |
| LoopGenerator | loop_reds, loop_spot_pos_{1,2}_{x,y} | amp |
| ImpulseGenerator | impulse | amp, duty |

WaveGenerator instances by source builder (matches `patching/*.py`):

| Builder | Instances |
|---|---|
| reds | sin_red |
| washes | sin_wash, sqr_wash |
| plants | sin_plants, sq_{1-3} |
| booth | sin_booth |
| spots | sin_spot, sqr_spot, sin_spot_pos_{1-4} |
| chandelier | sin_chand_{1-3} |

Custom per-class params, preset-saved (added on top of the standard list above):

| Address | Type |
|---|---|
| `/gen/FFTGenerator/{name}/bounds` | 4-tuple `(low, 0, high, 0)` — the zeros are placeholders the OSC layout's bounds widget requires |
| `/gen/LoopGenerator/{name}/samples` | list |

Class-level fan-out, preset-saved:

| Address | Fans to |
|---|---|
| `/gen/FFTGenerator/lpf_alpha` | fft_1, fft_2 |

Actions (one row per family, with the concrete instance addresses inline):

| Address | Effect |
|---|---|
| `/gen/BPMGenerator/{bpm_name}/snap` — `bpm_red`, `bpm_wash` | every wave subscribed to this BPM snaps its period (see snap subscriptions below) |
| `/gen/LoopGenerator/{name or record_group}/record` — `loop_reds`, `loop_spot_pos_1`, `loop_spot_pos_2` | start/stop recording; paired x/y loops share a `record_group` so one toggle drives both |
| `/gen/LoopGenerator/{name or pair}/input` — `loop_reds` (scalar), `loop_spot_pos_1` (XY pair), `loop_spot_pos_2` (XY pair) | live value input; records the sample during capture |
| `/gen/ImpulseGenerator/impulse/punch` | fire a one-shot impulse |

BPM snap subscriptions (each wave that called `WaveGenerator.register_snap_to(bpm, osc)` registers a fan-out handler at the BPM's snap address):

| Snap address | Waves that snap |
|---|---|
| `/gen/BPMGenerator/bpm_red/snap` | sin_red, sin_plants, sin_booth, sin_spot, sqr_spot, sin_spot_pos_{1-4}, sin_chand_{1-3}, sq_{1-3} |
| `/gen/BPMGenerator/bpm_wash/snap` | sin_wash, sqr_wash |

## `/chan/{fixture}/{attr}/offset` — Mix channel offsets

Preset-saved binds for every real mix channel. `ChannelLevelsBuilder` walks `mixer.mix_channels` and registers `MixChannel.register_offset(osc, on_change)` for each non-virtual channel; the spot builder owns the virtual `pantilt` registration itself. Channel names use `/` as the fixture/attribute separator (not `.`) so `@{chan/…/offset}` references work in Open Stage Control — OSC parses dots in `@{id}` as JS property access.

Real channels:
- LightFixture dimming: `chan/{fixture}/dimming/offset` — `left_{1-4}`, `right_{1-4}`, `front_{1,2}`, `under_{1,2}`, `ceil_{1-3}`, `chand_{1-3}`, `tung_spot`, `pin_1`, `sodium`
- RGB(W) wash dimming: `chan/{wash}/dimming/offset` — `wash_fl`, `wash_fr`, `wash_ml`, `wash_mr`, `wash_bl`, `wash_br`, `wash_ceil_f`, `wash_ceil_r`
- YRXY200Spot: `chan/spot_{1,2}/dimming/offset`, `chan/spot_{1,2}/x_coord/offset`, `chan/spot_{1,2}/y_coord/offset` (x/y are mapping-space 16-bit values; `post_map_output` converts to real pan/tilt at DMX-write time)
- Hazer: `chan/hazer/output/offset`, `chan/hazer/fan/offset`
- Composite mono / stutter channels (no slash inside the channel name): `chan/reds_mono/offset`, `chan/reds_fwd/offset`, `chan/reds_back/offset`, `chan/reds_zig/offset`, `chan/washes_mono/offset`, `chan/washes_fwd/offset`, `chan/washes_back/offset`

Virtual pantilt addresses, preset-saved — `PantiltChannel` is a 2-vec `[x_coord, y_coord]` facade that writes through to the underlying mix channels and is skipped from `signal_patchbay` routing:

| Address | Underlying channels |
|---|---|
| `/chan/spot_{1,2}/pantilt/offset` | `spot_{1,2}/x_coord`, `spot_{1,2}/y_coord` |

## `/chan/{category}/stutter_period` — Stutter period per category

Preset-saved fan-out via `MixChannel.register_stutter_period(osc)`.

| Address | Channels sharing it |
|---|---|
| `/chan/reds/stutter_period` | reds_fwd, reds_back, reds_zig |
| `/chan/washes/stutter_period` | washes_fwd, washes_back |

## `/fixture/{ClassName}/{name}/{attr}` — Per-fixture params

Preset-saved binds via `Fixture.standard_params()`.

| Class | Instances | Attributes |
|---|---|---|
| YRXY200Spot | spot_1, spot_2 | color_index, pattern_index, prisim_enabled, prisim_rotation |
| RadianceHazer | hazer | target_output, target_fan, interval, duration |

`RGBLight`, `RGBWLight`, and `PinSpot` expose no per-instance attrs — color is set via the class-level broadcasts below.

## `/fixture/{ClassName}/{action}` — Class-level fixture broadcasts

Fan-out: each instance self-registers a handler. The color/w_target rows are preset-saved binds (`color_param()` / `w_target_param()`); `reset` is an action.

| Address | Payload | Fans to |
|---|---|---|
| `/fixture/YRXY200Spot/reset` | trigger | spot_1, spot_2 |
| `/fixture/RGBLight/color` | 3× float (r, g, b) | wash_fl, wash_fr, wash_ml, wash_mr, wash_bl, wash_br, wash_ceil_f, wash_ceil_r |
| `/fixture/RGBWLight/w_target` | float | wash_ceil_f, wash_ceil_r |
| `/fixture/PinSpot/color` | 3× float (r, g, b) | pin_1 |
| `/fixture/PinSpot/w_target` | float | pin_1 |

By default `RGBWLight` instances also listen on `/fixture/RGBLight/color` so one UI message drives every RGB-family wash. Pass `use_rgb_color_broadcast=False` to the constructor to isolate an instance to `/fixture/RGBWLight/color` instead.

## `/signal_patchbay/{category}` — Signal routing matrices

Preset-saved binds, one per patchable category, created via `Mixer.patchbay_param(category)`. Virtual channels (PantiltChannel) are excluded from routing.

Categories: reds, plants, booth, washes, spots_light, spots_position, chandelier.

## `/{category}_master` — Category master faders

Session-saved binds, created via `Category.master_param` during `Categories.__init__`.

Categories: reds, plants, booth, spots_light, washes, spots_position, washes_color, audio, strobes, hazer, chandelier, non-saved.

(The category literally named `non-saved` still gets a session-saved master fader like the others — its name refers to *preset* persistence, not session persistence.)

## `/scene/{name}` — Scene triggers

Actions, served by `dispatcher.map("/scene/*", ...)`. The wildcard handler looks up `name` in the scene dict and calls `scene.activate()` (sets category masters, optional channel offsets, optionally disables DMX passthrough, applies a preset group). The `name` segment is the scene's display name verbatim, including spaces.

Built-in scenes registered in `server.py`:

| Address | Preset group | Notes |
|---|---|---|
| `/scene/All Black` | Off | zeroes every master, sodium offset → 0 |
| `/scene/House Lights` | Static | masters up, sodium → 255, disables DMX passthrough |
| `/scene/Class Lights` | Class | partial masters, disables DMX passthrough |

User-created scenes (loaded from `scenes.pickle`) appear at the same `/scene/{name}` pattern.

## `/scene/...` — Scene management

Actions plus the dropdown bind for picking and listing scenes.

| Address | Direction | Purpose |
|---|---|---|
| `/scene/create` | UI → Server | capture current state as a scene; payload is the scene name string |
| `/scene/save_current` | UI → Server | overwrite the currently selected scene |
| `/scene/clear_current` | UI → Server | delete the currently selected scene |
| `/scene_selector` | bidirectional | echo / select the active scene name |
| `/scene_selector/values` | Server → UI | scene-name → name dict for the dropdown |

## `/preset/...` — Preset management

| Address | Direction | Purpose |
|---|---|---|
| `/preset/save/{category}` | UI → Server | save current state as preset |
| `/preset/clear/{category}` | UI → Server | delete the selected preset |
| `/preset/selector/{category}` | bidirectional | select / echo current preset name |
| `/preset/reload` | UI → Server | re-sync every preset-tracked param to the frontend (also resyncs the scene dropdown) |
| `/preset/restore_defaults` | UI → Server | overwrite the active pickle with `default-params.pickle` and reload (gated by `/enable_save`) |

## `/coord_system` — Active coord system selector

Bidirectional bind from `CoordSystemState`. Value is the active `CoordSystem` name (e.g. `"pantilt"`, `"latlon"`). Persists in the session pickle; intentionally not preset-saved (it's a UI / shell preference, decoupled from preset state). Setting it triggers `rebind_coords(old, new)` on every registered fixture so spots stay still across the toggle.

## `/visualizer/...` — Data streams and enables

Server → UI streams (sent via `send_osc`, gated by heartbeat — see the `enable_*` rows below):

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
| `/visualizer/fixture/{spot}/pantilt` | spot_1, spot_2 — `[pan, tilt]` real DMX-space ints (post coord conversion, not the mapping-space x/y) |

UI → Server enables and source select:

| Address | Purpose |
|---|---|
| `/visualizer/enable_fft_spectrum` | heartbeat to gate the spectrum + audio-analysis streams (`/visualizer/fft`, `/visualizer/fftgen_{1,2}`, `rms/bpm/harmonic_percussive/business/regularity` histories) |
| `/visualizer/enable_fft_gen_timeseries` | heartbeat to gate `/visualizer/fftgen_{1,2}_history` |
| `/visualizer/enable_synth` | heartbeat to gate `/visualizer/synth_history` |
| `/visualizer/enable_fixture` | heartbeat to gate fixture dimming/pantilt streams |
| `/visualizer/synth_source` | bind selecting which channel feeds `synth_history` (non-saved category) |

The four `enable_*` heartbeats are driven by the top-level tab switcher's `onValue` script, which sends `1` for the matching tab index and `0` otherwise. The server only treats `1` as a heartbeat (extends the gate by ~2s); `0` messages are ignored so a second UI client on a different tab can't yank the gate closed.

## `/audio_config/...` — Audio + FFT configuration

Preset-saved binds via `FFTManager.config_params()`:

`bpm_energy_threshold`, `bpm_tempo_alpha`, `bpm_phase_alpha`, `onset_envelope_floor`, `bpm_business_min`, `bpm_regularity_min`, `bpm_outlier_window`, `bpm_publish_interval`.

Actions: `start_audio`, `stop_audio`, `start_fft`, `stop_fft`, `port_refresh`.

Port selection: standard `port_name` + `port_name/values` pattern (see Conventions).

## `/dmx/...` — DMX port configuration

`/dmx/passthrough` is bound via `DMXManager.passthrough_param()` and lives in the `non-saved` category, so it is not preset-saved.

Actions: `port_refresh`, `port_disconnect`.

Port selection: standard `port_name` + `port_name/values` pattern (see Conventions).

## `/debug/...` — Debug UI frames

`/debug/fft_frame`, `/debug/audio_frame` — `UIDebugFrame` heartbeat containers (server → UI with debug metrics).

## Root-level addresses

| Address | Direction | Purpose |
|---|---|---|
| `/heartbeat` | UI → Server | client keep-alive (sent every 2s from `onCreate`) |
| `/client_count` | Server → UI | connected client count |
| `/enable_save` | bidirectional | toggle preset save/clear UI; gates `/preset/restore_defaults` and scene save/clear |

## Frontend-only fan-outs

Widgets in `open-stage-control/layout-config.json` that send to additional addresses via `onValue` scripts — not part of the server's address scheme, just UI ergonomics.

| Widget / control | Sends to |
|---|---|
| Top-level tab switcher | `/visualizer/enable_fft_spectrum`, `/visualizer/enable_fft_gen_timeseries`, `/visualizer/enable_synth`, `/visualizer/enable_fixture` (one address per active-tab index) |
| Scene dropdown | `/scene/{value}` whenever a scene name is picked |
| Scene name buttons | `/scene/create`, `/scene/save_current`, `/scene/clear_current` |
| Spot pantilt nudge buttons (per spot, 4 directions) | `/chan/spot_{1,2}/pantilt/offset` (read-modify-write by `spot_{1,2}_nudge_step`) |
