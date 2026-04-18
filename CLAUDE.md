# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo layout

- `python/parquette-lights/` — main Python server (Poetry project, package `parquette.lights`). This is the main codebase and the backend server. It orchestrates a DMX lighting system in conjuection with a web UI based on open stage control
- `open-stage-control/` — Open Stage Control front-end config. `layout-config.json` is the UI layout; other files are server/UI initial state.
- `launchd/` — launchd plists + `install` script for auto-running the server and Open Stage Control on the mac mini.
- `esp/` — ESP-based hardware sketches (`controller_base`, `address_changer`, `i2c_scanner`). These will be used to create hardware interfaces sending OSC controls to the server. This can be ignored for now
- `python/parquette-lights/params.pickle` — persisted preset state. Auto-written when presets are saved/cleared in the UI; commit it to persist.

## Common commands

All run from `python/parquette-lights/`:

- `poetry sync` — install deps
- `poetry run server` — run the lighting server (entry: `parquette.lights.server:run`). Useful flags: `--local-ip 0.0.0.0`, `--entec-auto /dev/tty.usbserial-...`, `--art-net-ip`, `--boot-art-net`.
- `poetry run poe check` — runs black, pylint, mypy in sequence (continues on failure)
- `poetry run poe black` - runs black code formatter
- `poetry run poe mypy` - runs mypy and checks for typing issues 
- `poetry run poe pylint` - runs pylint and checks for issues
- `poetry run poe pytest` - runs the test suite
- `poetry run poe strip-osc-layout` — runs `scripts/strip_layout_defaults.py` to clean up the OSC layout JSON

## Architecture

The server (`parquette.lights.server`) wires together a small pipeline:

- **AudioCapture** (PortAudio via pyaudio) feeds raw audio into **FFTManager** (`audio_analysis/`), which produces frequency-band features.
- **FFTManager** analyses this raw audio with the help of the librosa framework. This creates various audio reactive signals to be used for orchestrating and in generators
- **Generators** (`generators/`) turn signals (either time series functions or audio reactive) into per-fixture color/intensity values, although the signals can be used also to control other parameters such as position. Types include `FFTGenerator`, `WaveGenerator`, `ImpulseGenerator`, `BPMGenerator`, plus a `Mixer` and `SignalPatchParam` for routing. `generator.py` defines the base class.
- **Fixtures** (`fixtures/`) model physical lights — `RGBLight`, `RGBWLight`, `YRXY200Spot`, `Spot`, `RadianceHazer`, etc. They convert generator outputs into DMX channel values.
- **DMXManager** (`dmx.py`) outputs to either an Enttec DMX USB Pro (via `dmxenttecpro`) or Art-Net (via `stupidartnet`).
- **OSCManager** (`osc.py`) handles bidirectional OSC with Open Stage Control. Parameters are wrapped as `OSCParam` so UI controls and server state stay in sync.
- **PresetManager** (`preset_manager.py`) serializes/loads parameter state to `params.pickle`.
- **ClientTracker** (`util/client_tracker.py`) tracks connected OSC clients so UI state can be re-pushed on reconnect.

The Open Stage Control front-end (in `open-stage-control/layout-config.json`) is the UI; it talks to the server over OSC. Web UI is served at port 8080 by Open Stage Control, server listens for OSC on 5005 and sends to OSC on 5006 by default.

## Conventions

- Python ≥ 3.10, formatted with black, linted with pylint (config: `pylintrc`), typed with mypy.
- When editing fixtures or generators, keep DMX channel layout and OSC parameter names consistent — both the layout JSON and `params.pickle` reference them by name.
- Changes to presets are committed via `params.pickle` to persist across deploys, but the presets are configured by the user. We are not very concerned with schema migration issues for the params, they can just be rebuilt if needed.
- Don't use _ named variables and function, assume all functions and variable are public
- When creating parameters that need to be controlled by the front end, create them as OSCParam and include them in the preset manager so they can be saved and sync'd with the front end
- When creating parameters assume you need a front end UI element (slider or similar) in the associated tab and that UI element should also have a text area under it with a name and a real time value
- Use OSCParam.obj_param_setter with OSCParam where possible to avoid redundant code
- When making changes to python code we should always run `poetry run check` to format code and check for errors. We should also run `poetry run poe pytest` and check for any test errors and `poetry run poe test-ui`
- Code written should use mypy typing hints
- If you don't see the root cause for a bug don't make changes guessing at the solution, only describe possible debugging approaches.
- Always try and write object oriented, reusable code. Breakup functions and classes if they are becoming too large. We are trying to make maintable code.
- When writting comments do not reference claude plans or dialogue with claude in the comment. Instead write comments that will make sense to someone reading the code with no prior context.
- When editing the front end don't change the position of existing UI elements, always check their position because the user may have adjusted it since last edits, and keep that position. New UI elements should be at the bottom not overlapping anything else. If using pannels assume that the pannel needs some internal margin.
- When adding widgets to the OSC layout, ensure all widget IDs are globally unique across the entire layout file. Open Stage Control uses the ID as the OSC address when `address` is set to `"auto"`, so duplicate IDs cause widgets to receive each other's values. Prefix IDs with the tab or section name to avoid collisions (e.g., `viz_label_left_1` instead of `textarea_1`).
- In Open Stage Control widget properties, use `@{widget_id}` to reference another widget's value. For dynamic JS expressions, use the `#{}` shorthand which auto-returns the expression result, e.g. `#{'RGB ' + @{wash_rgb_picker}.map(v => Math.round(v)).join(', ')}`. Do not mix literal text outside `#{}` — the entire value must be inside the block. For multi-statement scripts use `JS{ ... return val; }`.
- Don't use if TYPE_CHECKING, structure code without circular imports or stop on circular imports and discuss how to avoid them
- When adding a new `patchbay` widget to `open-stage-control/layout-config.json`, copy the shared `css` block from an existing patchbay (e.g. `signal_patchbay/reds`). It widens the input/output node panels to 30% of the container each and enables word-wrap on node labels so long names like `wash_ceil_f.dimming` don't truncate.

## Adding a new fixture category

When adding a new category with fixtures and generators, follow these steps. Use an existing simple category like `plants` or `chandelier` as a reference.

### 1. Register the category (`category.py`)
- Add `self.<name> = Category("<name>", osc, session)` in `Categories.__init__`
- Add it to `self.all` list (before `non_saved`)
- This auto-creates the `/<name>_master` OSCParam for the master fader

### 2. Create the builder (`patching/<name>.py`)
- Subclass `CategoryBuilder`
- In `__init__`: create fixtures (e.g. `LightFixture`), generators (e.g. `WaveGenerator`), and wire cross-object behavior (`register_snap_to`, etc.)
- Implement `fixtures()` → returns all fixtures
- Implement `generators()` → returns all generators
- Implement `build_params(mixer)` → returns `{self.category: [mixer.patchbay_param(self.category), *gen.standard_params(osc), ...]}`. Every OSCParam in this list becomes preset-saveable

### 3. Register the builder (`patching/__init__.py`)
- Import the new module
- Add the builder to the list in `create_builders()`, before `channel_levels` (which must be last among real builders since it iterates all mix channels)

### 4. Add UI widgets (`open-stage-control/layout-config.json`)
All new widgets need globally unique IDs. Add to these tabs:

- **tab_preset**: Preset panel with `preset/selector/<name>` switch, `preset/save/<name>` button, `preset/clear/<name>` button, and a `<name>_master` fader (duplicated across tabs — add to `ALLOWED_DUPLICATE_IDS` in `tests/ui/test_layout_structure.py`)
- **tab_master_levelss**: Master fader `<name>_master` + label
- **tab_synth_controls**: `signal_patchbay/<name>` patchbay (with shared CSS) listing generator inputs and `<fixture>/dimming` outputs, plus generator control panels (amp/period faders + labels + snap-to-bpm button per generator)
- **tab_chan_offsets**: A `<name>_master` fader at the left, then a **panel** container (e.g. `chandelier_group`) with a title textarea (e.g. "Chandelier") at (5,5), then per-channel offset faders (`chan/<fixture>/dimming/offset`) starting at (10,30) spaced 85px apart horizontally, with labels at top:235. Copy the structure from an existing group like `booth_group`

### 5. Add fixtures to the visualizer (`open-stage-control/layout-config.json`)
- In `tab_visualizer`, add a panel per fixture following the `viz_{name}` pattern (e.g. `viz_chand_1`)
- Each panel has `layout: "horizontal"`, contains a compact fader (`visualizer/fixture/{name}/dimming`, range 0-255, interaction: false) and a label textarea (`viz_label_{name}`)
- Group related fixtures together spatially. Copy structure from an existing panel like `viz_sodium`

### 6. Add the category master to scenes (`server.py`)
- Find the `Scene(...)` instantiations (all_black, house_lights, class_lights)
- Add `categories.<name>: <value>` to each scene's `masters` dict:
  - `all_black`: set to 0
  - `house_lights`: set to appropriate level (typically 1)
  - `class_lights`: set to appropriate level (e.g. 0.5)

### 7. Update tests
- Add `<name>_master` and `<name>_master_text` to `ALLOWED_DUPLICATE_IDS` in `tests/ui/test_layout_structure.py`

### 8. Verify
- `poetry run poe check` — formatting, lint, types
- `poetry run poe pytest` — unit + UI tests
- `poetry run poe test-ui` — UI-specific tests