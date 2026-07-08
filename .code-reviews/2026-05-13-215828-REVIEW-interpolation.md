# Code Review: Scene-Fade Interpolation

**Scope**: Interpolation-related portions of the in-progress (unstaged) changes on `main`. Diffed against `HEAD` per the caller's instruction (repo is currently in a `git bisect` state).

**Verdict**: **fixes needed before merge.** The end-to-end feature works for the typical "fade scene over a second" UX, but there are several correctness issues that will bite under reasonable use: an exception-safety hole in `OSCParam.load` that can leak `pending_fade_ticks` and make subsequent setter calls silently interpolate; user-fader overrides on `Category.master` getting clobbered by an in-flight scene fade; and a hardcoded default `tick_ms=20.0` in `SceneManager` that produces wrong fade durations if you ever change `--tick-ms` and forget to set it on `SceneManager`. The publishing of `osc.send_osc` directly from `tick_interpolators` also splits the OSC path between `OSCParam.sync()` and direct sends in a way that's likely to grow into a bug source as more interpolated quantities appear.

## Table of contents

- [1. OSCParam / `pending_fade_ticks` plumbing](#1-oscparam--pending_fade_ticks-plumbing)
- [2. Category master interpolation](#2-category-master-interpolation)
- [3. MixChannel offset interpolation](#3-mixchannel-offset-interpolation)
- [4. Fixture color interpolation](#4-fixture-color-interpolation)
- [5. SceneManager fade configuration](#5-scenemanager-fade-configuration)
- [6. SignalPatchParam load signature](#6-signalpatchparam-load-signature)
- [7. Interpolator primitive](#7-interpolator-primitive)
- [8. Layout JSON](#8-layout-json)
- [9. Tests](#9-tests)
- [Resolution Plan](#resolution-plan)

---

## 1. OSCParam / `pending_fade_ticks` plumbing

### B1 — `pending_fade_ticks` leak if `dispatch_lambda` raises (`osc.py:117-130`)

```python
def load(
    self, addr: str, *osc_args: Any, sync: bool = True, fade_ticks: int = 0
) -> None:
    self.fade_ticks = fade_ticks
    if fade_ticks > 0 and self.bind_targets is not None:
        for t in self.bind_targets:
            if hasattr(t, "pending_fade_ticks"):
                t.pending_fade_ticks = fade_ticks
    self.dispatch_lambda(addr, *osc_args)        # ← unguarded
    if fade_ticks > 0 and self.bind_targets is not None:
        for t in self.bind_targets:
            if hasattr(t, "pending_fade_ticks"):
                t.pending_fade_ticks = 0
    self.fade_ticks = 0
```

If `dispatch_lambda` raises (a bad-shape value off the wire, a setter that does something IO-y like `osc.send_osc` and gets a socket error, etc.), `pending_fade_ticks` stays set on every bind target. From then on, *every* setter call on those targets — including user UI input and non-scene flows — will silently interpolate over the now-stale fade tick count, possibly for the full lifetime of the process.

Wrap the dispatch + reset in `try/finally`:

```python
self.fade_ticks = fade_ticks
self._set_pending_fade(fade_ticks)
try:
    self.dispatch_lambda(addr, *osc_args)
finally:
    self._set_pending_fade(0)
    self.fade_ticks = 0
if sync:
    self.sync()
```

This is a bug, not a nit: `obj_param_setter` already swallows AttributeError but anything else (a TypeError from float conversion, an IndexError from `value[0]` on a malformed color message) propagates out and triggers the leak.

### H1 — `OSCParam.fade_ticks` is write-only dead state (`osc.py:106, 120, 130`)

`self.fade_ticks` is assigned by `__init__` and `load`, but never read by anyone. It contributes to confusion (why is there both `self.fade_ticks` and a `fade_ticks` parameter?) and adds work to every `OSCParam` construction. Drop the field; keep only the `load` parameter.

### M1 — `OSCParam.load` won't pass `fade_ticks` through overridden subclass `load` signatures by name (`generators/mixer.py:494-506` cross-reference)

Right now the only subclass override is `SignalPatchParam.load`, which was patched in this PR to accept `fade_ticks`. Any future `OSCParam` subclass that overrides `load` without the keyword will silently break preset loading the moment it ends up in `exposed_params`. Worth a one-line comment in `OSCParam.load` ("subclasses overriding load must accept fade_ticks") and a unit test that exercises `param.load(addr, value, sync=False, fade_ticks=10)` for every concrete subclass.

### M2 — `bind_targets` is `Optional[List[Any]]` but binders always pass a list (`osc.py:107, 159, 180`)

`OSCParam.__init__` declares `bind_targets: Optional[List[Any]] = None`, then `bind` always sets it to a non-empty list. Every reader (`if self.bind_targets is not None`) therefore special-cases a case that only occurs for directly-constructed params (e.g. `SignalPatchParam`). Cleaner: default to `[]` in `__init__` and drop the `is not None` checks. Same end behavior, less noise.

### L1 — Use `Iterable[Any]` / a private helper for the `pending_fade_ticks` write loop (`osc.py:121-129`)

The two near-identical loops (set, then reset) duplicate the `bind_targets is not None` and `hasattr` checks. A two-line helper makes the intent ("propagate fade to every target that opts in") obvious and avoids drift between the set and reset paths:

```python
def _propagate_fade(self, ticks: int) -> None:
    if self.bind_targets is None:
        return
    for t in self.bind_targets:
        if hasattr(t, "pending_fade_ticks"):
            t.pending_fade_ticks = ticks
```

### N1 — Inconsistent `hasattr` style (`generators/chanmap.py:130`, `osc.py:123`)

`MixChannel.tick_interpolator` uses `hasattr(self, "offset_osc_param") and self.offset_osc_param is not None` even though `offset_osc_param` could just be initialized to `None` in `__init__`. Same for the `pending_fade_ticks` checks elsewhere — they assume the attribute might be missing. The base `Fixture` already initializes `pending_fade_ticks = 0` in `__init__`, so the `hasattr` in `MixChannel.offset.setter` (line 112) and in `OSCParam.load` could be `getattr(t, "pending_fade_ticks", 0)` or made unconditional by initializing the attribute on every bind target. Pick one style.

## 2. Category master interpolation

### H2 — User UI overrides during an in-flight master fade are silently clobbered (`category.py:35-48`, indirectly via `osc.py:184-191`)

`Category` has no `master` property — `OSCParam.bind(self, "master")` writes through `obj_param_setter` directly into `self.__dict__["master"]`, never touching `master_interp`. So:

1. A scene activates with `fade_ticks=50`.
2. `master_interp` starts walking from `1.0` toward (say) `0.0` over 50 ticks.
3. At tick 10, the user grabs the master fader in the UI and moves it to `0.5`.
4. `obj_param_setter` writes `self.master = 0.5` directly.
5. Tick 11: `tick_interpolator` sees `master_interp.active`, calls `master_interp.tick()`, overwrites `self.master` with the interpolator's next value. The user's input is gone.

Result is a master fader that resists the user mid-fade. Fix options:

- Convert `Category.master` to a property and have its setter `self.master_interp.set_target(value, 0)` (mirroring `MixChannel.offset` setter, which cancels in-flight fades on direct writes).
- Or in `tick_interpolator`, detect that `self.master` was changed externally (e.g. compare against the previously-emitted value) and bail.

Option 1 is the consistent fix — `MixChannel.offset` already does this exact cancellation pattern.

### M3 — `set_master` fade>0 path skips initial sync (`category.py:37-42`)

```python
if fade_ticks > 0:
    self.master_interp.set_target(value, fade_ticks)
else:
    self.master = value
    self.master_interp.set_target(value)
    self.master_param.sync()
```

When the fade path is taken, `self.master` is unchanged until the next tick and the UI is not synced. The first `tick_interpolator()` then advances + syncs, so the UI starts animating one tick late (20 ms). Probably imperceptible at 50 Hz, but for completeness a single `self.master_param.sync()` (which would emit the unchanged starting value) wouldn't help anyway since the UI is already at that value. The real issue is **not** syncing — it's that `set_master` does **not** start the interpolation at "the current master value." It implicitly assumes `master_interp.current == self.master`, which is true on first call but could drift if anyone ever wrote to `self.master` between fades. (Today nothing does, so this is latent.) Worth a comment or an explicit `self.master_interp.current = self.master` before `set_target` to harden the invariant.

### L2 — Double bookkeeping between `Category.master` and `Category.master_interp.current` (`category.py:24-25, 47`)

There are now two sources of truth that must be kept in sync (`self.master` and `self.master_interp.current`). The same pattern appears for `MixChannel._offset_storage` vs `MixChannel.offset_interp.current`. It works today but it's a class of bug factory. Worth considering, in a follow-up, replacing the backing field with a `@property` that returns `master_interp.current` directly (the way `RGBLight.r_target` is now structured). That would make the invariant unfakable.

## 3. MixChannel offset interpolation

### M4 — `offset_osc_param` initialized in `register_offset`, not `__init__` (`generators/chanmap.py:170`)

```python
def register_offset(self, osc, on_change=None) -> OSCParam:
    self.offset_osc_param: Optional[OSCParam] = None
    param = OSCParam.bind(...)
    self.offset_osc_param = param
    return param
```

The type-annotated assignment outside `__init__` is unusual (pylint typically flags `attribute-defined-outside-init`) and is the reason `tick_interpolator` has to do the `hasattr` dance. Initialize `self.offset_osc_param: Optional[OSCParam] = None` in `MixChannel.__init__`. Then `tick_interpolator` can do `if self.offset_osc_param is not None:` cleanly.

### M5 — `PantiltChannel` participates in the offset-fade pipeline by accident (`generators/chanmap.py:210-243`)

`PantiltChannel` is a virtual `MixChannel` with `offset` as a 2-vec (pan, tilt). It inherits `pending_fade_ticks` and `offset_interp` from the base, but its `offset` setter does **not** route through them — it writes the two scalar values to the real `pan_channel.offset` and `tilt_channel.offset`. Two problems fall out:

1. If `OSCParam.load(fade_ticks=N)` is called on the pantilt param, the loader sets `pantilt.pending_fade_ticks = N`, dispatches the setter, which writes to pan/tilt. But pan/tilt have their **own** `pending_fade_ticks = 0`, so the writes snap. So pantilt is silently un-faded even when caller asked to fade. (Probably fine for moving heads, but undocumented.)
2. `pantilt.tick_interpolator` runs every tick from the main loop. It checks `offset_interp.active` (always false for pantilt since the setter never touches the interp) — so harmless, but a minor waste of cycles.

Worth either (a) overriding `tick_interpolator` to a no-op on `PantiltChannel` for clarity, or (b) propagating `pending_fade_ticks` from pantilt down into pan/tilt when its setter fires. (b) is the more useful direction long-term but isn't required for correctness today.

### L3 — `offset` setter always re-targets the interpolator on snap path (`generators/chanmap.py:115-117`)

```python
else:
    self._offset_storage = float(value)
    self.offset_interp.set_target(float(value))
```

The `set_target` call with implicit `ticks=0` is intentional — it cancels any in-flight fade by snapping `interp.current` to `value`. Worth a one-line comment so future readers don't "simplify" this and remove the cancellation.

## 4. Fixture color interpolation

### H3 — `tick_interpolators` broadcasts OSC outside the `OSCParam.sync()` machinery (`fixtures/basics.py:263-269, 389-402`; `fixtures/spotlights.py:1097-1110`)

```python
def tick_interpolators(self) -> None:
    active = self.r_interp.active or self.g_interp.active or self.b_interp.active
    self.r_interp.tick()
    ...
    if active and self.osc is not None:
        self.osc.send_osc(self.color_osc_addr, self.color)
```

The cached `color_osc_addr` is `/fixture/{ClassName}/color` — the same address `color_param()` binds to. Every tick during a fade, *every fixture of that class* sends to this address. With N instances of `RGBLight`, that's N near-identical OSC messages per tick (~50 Hz). On the wire that's wasteful (the value is the same across instances when the broadcast bind is in use); in the UI the picker just sees a flurry of redundant updates.

But more importantly, this bypasses the `OSCParam.sync()` machinery, which means:

- The corresponding `OSCParam`'s `value_lambda` is never consulted.
- `on_change` callbacks (notably `session.save` for some params) are not invoked.
- It's now possible for the *same* logical value to be pushed to the UI via two different paths (the `OSCParam.sync()` issued from `preset_manager.sync()` at the start of a fade, then 50 Hz of direct sends from `tick_interpolators`).

For RGBWLight with `use_rgb_color_broadcast=True`, all RGBLight + RGBWLight instances broadcast to `/fixture/RGBLight/color` from their own `tick_interpolators`. If a scene fade is in flight across both, the UI receives the *last fixture's color value*, which is fine if all instances are fading to the same color but ill-defined if they're not.

The cleaner architecture is to either:

- Have the fixture call `self.color_osc_param.sync()` (requires storing the bound OSCParam on the fixture, the way `MixChannel` now stores `offset_osc_param`).
- Or only have **one** fixture per broadcast class emit (e.g. the first one), to avoid N-way duplication.

This is currently the most architecturally fragile piece of the change.

### H4 — `r_target` / `g_target` / `b_target` getters change return type semantics (`fixtures/basics.py:200-222`)

Previously `r_target: DMXValue = 255` (an `int`). Now the getter returns `self.r_interp.current` which is always a `float`. Downstream consumers:

- `RGBLight.color` returns `[float, float, float]` instead of `[int, int, int]`. The preset save pickles whatever the getter returns; reloading a preset built before this change is fine (it's still `[int, int, int]` on disk), but **a preset saved after this change will contain floats**, which means the `param.is_at_default()` comparison `value_lambda() == self.default_value` will now compare `[255.0, 255.0, 255.0] == [255, 255, 255]` — Python says `True` for that case but the moment an interpolation lands at e.g. `254.99999998` (floating-point), `is_at_default()` flips to False and presets save the spurious value.
- `RGBLight.dimming(val)` does `value_map(val, 0, 255, 0, self.r_target)` where `self.r_target` may be a fractional float. `value_map` returns a float. `self.set([r,g,b])` ultimately routes through `dmx.set_channel` which does `int(constrain(v, 0, 255))`. So DMX is fine, but any caller checking color equality is at risk.
- Visualizer / UI: OSC senders just send the float, which Open Stage Control should display fine.

The pragmatic fix is for the getter to round on read (`return int(self.r_interp.current)`), or to keep `Interpolator.current` as float but expose targets as `int`. Either way, store the **target** integer separately so `is_at_default()` and preset diffing stay exact.

### M6 — `set_dimming_target` is now keyword-only but callers in patching code may break (`fixtures/basics.py:248-261, 371-387`; `fixtures/spotlights.py:1079-1095`)

Adding the `*` after `self` is a breaking change for any caller using positional args. A repo grep shows no current positional callers, but:

```python
def set_dimming_target(
    self,
    *,
    r: Optional[DMXValue] = None,
    ...
```

If any external script or test passes `set_dimming_target(255, 255, 255)`, it now raises `TypeError`. The CLAUDE.md convention discourages `pylint: disable=too-many-positional-arguments` in favor of keyword-only, so this aligns with project style — but worth a `git grep` to confirm no positional callers were missed. (My check found none, but it's worth double-checking before merge.)

### L4 — `Spot` (moving-head color wheel) is not fade-capable (`fixtures/spotlights.py:22+`)

Scene fades won't fade moving-head colors — the color wheel index snaps. This may be intentional (the wheel is mechanical) but worth a comment in `Spot.color()` explaining why this fixture is excluded from the fade pipeline.

### L5 — `pending_fade_ticks` is a side-channel rather than an explicit parameter (`fixtures/basics.py:71, 205, 213, 221, 235`)

The whole `pending_fade_ticks` mechanism exists because the property-setter signature (`r_target = X`) doesn't have anywhere to put a `fade_ticks` argument. So `OSCParam.load` sets a flag on the target, the setter reads it, then `OSCParam.load` clears it. This works but couples `OSCParam`, the target fixture, and the setter via a shared mutable attribute. The explicit method (`set_dimming_target(r=X, fade_ticks=N)`) is much clearer. Worth considering whether the `pending_fade_ticks` side-channel is actually necessary — `preset_manager.select` could route through the explicit method for fixtures that support it. (Bigger refactor; flagging as `[Manual]` in the plan.)

## 5. SceneManager fade configuration

### B2 — `SceneManager.tick_ms` default of `20.0` will silently produce wrong fade lengths (`scene.py:142`, `server.py:343`)

```python
# scene.py
self.tick_ms: float = 20.0

# server.py
scene_manager = SceneManager(...)
scene_manager.tick_ms = tick_ms
```

If `server.py` is ever refactored so the `scene_manager.tick_ms = tick_ms` assignment is dropped or moved (e.g. for tests, alternative entry points, sub-process workers), `SceneManager` falls back to a hardcoded `20.0` that almost certainly mismatches the actual `chanmap_module.TICK_MS`. `fade_ms / tick_ms` then gives the wrong tick count and fades run too long or too short.

Fix: make `tick_ms` a required `SceneManager.__init__` argument. There's no good reason to allow construction without it.

### H5 — `fade_ms` clamps to a single tick at very short durations (`scene.py:173-177`)

```python
def fade_ticks(self) -> int:
    if self.fade_ms <= 0 or self.tick_ms <= 0:
        return 0
    return max(1, int(self.fade_ms / self.tick_ms))
```

`int(...)` truncates toward zero, then `max(1, ...)` raises it. So:

- `fade_ms = 5`, `tick_ms = 20` → `int(0.25) = 0` → `max(1, 0) = 1` tick (i.e. 20 ms — 4× the requested 5 ms).
- `fade_ms = 25`, `tick_ms = 20` → `int(1.25) = 1` tick (20 ms instead of 25).

`int()` should be `round()` to minimize bias. The `max(1, ...)` is fine as a "any positive request fades over at least one tick" rule.

### M7 — `fade_ms` UI fader is `snap: true` with no step size, so it floats between integer values (`open-stage-control/layout-config.json:266-273`)

The fader range is `0..5000`, integer-display (`decimals: 0`), with `snap: true` but no `steps`. The textarea label `"Fade @{scene/fade_ms}ms"` will render fractional values because the fader can land on `1234.567`. Add `"steps": "1"` (or similar) for crisp 1 ms resolution.

### L6 — `set_fade_ms(value)` does no validation (`scene.py:167-171`)

Accepts any float, including negative or `NaN`. Negative is harmless (`fade_ticks()` returns 0), but a future change could break that invariant. A `max(0.0, value)` clamp is cheap insurance.

### L7 — `SceneManager.sync` now sends `/scene/fade_ms` every time (`scene.py:308`)

`sync` is called on `register_scene`, after `create_scene`, after `clear_scene`, and on `/preset/reload`. Each invocation pushes the current fade_ms to the UI, even when it hasn't changed. Harmless but unnecessary chatter; OK as-is.

## 6. SignalPatchParam load signature

### M8 — `SignalPatchParam.load` accepts `fade_ticks` and silently ignores it (`generators/mixer.py:494-506`)

```python
def load(self, addr: str, *args: Any, sync: bool = True, fade_ticks: int = 0) -> None:
    # fade_ticks ignored — patch matrix can't be linearly interpolated
```

Pure signature-compatibility add. Worth a one-line comment explaining the intent (patch routing is discrete, can't be interpolated), otherwise a future reader will look for a missing implementation.

## 7. Interpolator primitive

### M9 — `tick()` decrements then snaps without using `step` for the last step (`util/interpolator.py:26-34`)

```python
def tick(self) -> float:
    if self.active:
        self.remaining_ticks -= 1
        if self.remaining_ticks == 0:
            self.current = self.target
        else:
            self.current += self.step
    return self.current
```

Two correctness consequences:

1. **Float drift on the penultimate tick is bounded.** Setting `current = target` at the last tick guarantees the final value is exact, regardless of accumulated float error from `current += step`. Good defensive design.
2. **But the size of the *last* delta isn't `step`.** For an N-tick fade, the first `N-1` ticks each add `step = (target - start)/N`, and the last tick snaps to `target`. So tick `N` covers `step + accumulated_float_error`. In practice this is invisible (we're talking 8-bit DMX), but if an effect ever depended on uniform per-tick deltas (audio sync, beat-locked fades), it would notice. Worth a docstring note.

### L8 — `set_target(target, 0)` ambiguity (`util/interpolator.py:15-24`)

`set_target(target, 0)` is documented as "snap." It also (correctly) clears `remaining_ticks` and `step`. But `set_target(target, ticks=-1)` silently also snaps because of the `ticks <= 0` guard. That's defensive but undocumented. One-line docstring fix.

### N2 — `tick()` does `if self.active` then decrements (`util/interpolator.py:28-30`)

A micro-readability nit: `if self.remaining_ticks > 0` is what `active` resolves to, and reading it via the property in the hot path costs a Python attribute access. For a function called per-fixture per-tick at 50 Hz across maybe a hundred interpolators, an inline `if self.remaining_ticks > 0:` is marginally more honest about what's happening. Not worth fixing on its own.

## 8. Layout JSON

### L9 — `scene/fade_ms` widget ID with a slash and `address: "auto"` is functional but breaks the ID-as-name convention (`open-stage-control/layout-config.json:258`)

Most widget IDs in the file are underscored (`scene_selector`, `scene_create_btn`). The slash works because `address: "auto"` converts the ID directly into the OSC address (`/scene/fade_ms`). Two ways to handle it:

- Keep the slash — it makes the OSC address literal in the JSON, which is occasionally helpful.
- Switch to `scene_fade_ms` ID with an explicit `"address": "/scene/fade_ms"`, matching surrounding conventions.

Stylistic; pick what's consistent with the existing codebase.

### N3 — `scene_fade_ms_text` textarea has `address: "auto"` and no `bypass: true` on echo (`open-stage-control/layout-config.json:288`)

The textarea has `"bypass": true` (good) but `"address": "auto"` means it still publishes an `/scene_fade_ms_text` address whenever something changes. With `bypass: true` outgoing messages are suppressed, so this is fine — flagging only because the address pollution is meaningless.

## 9. Tests

### H6 — No unit tests for the new interpolation behavior

`Interpolator` is a leaf primitive that's trivially testable, and the fade-tick plumbing has several edge cases worth pinning:

- `Interpolator.set_target(target, ticks=0)` snaps and clears active.
- `Interpolator.set_target(target, ticks=N)` then `N` `tick()` calls lands exactly on `target` (no float drift).
- Retargeting mid-fade (`set_target(A, 10)`, 5 ticks, then `set_target(B, 10)`) works as expected.
- `OSCParam.load(fade_ticks=N)` sets and resets `pending_fade_ticks` on bind targets.
- `OSCParam.load(fade_ticks=N)` cleans up `pending_fade_ticks` even when `dispatch_lambda` raises (regression test for B1 above).
- `Scene.activate(fade_ticks=N)` causes Category masters and MixChannel offsets to interpolate.

`tests/conftest.py` already imports `fade`-related fixtures, so the test infrastructure exists. Strongly recommend adding tests for `Interpolator` at minimum.

---

## Resolution Plan

- [ ] **[B1]** Wrap `dispatch_lambda` in `try/finally` in `osc.py:117-130` to guarantee `pending_fade_ticks` resets on exception. **Worth fixing**: small change, prevents silent global state corruption.
- [ ] **[B2]** Make `tick_ms` a required `SceneManager.__init__` argument in `scene.py:122-138` and drop the `self.tick_ms: float = 20.0` default. Update `server.py:340-343` to pass `tick_ms=tick_ms`. **Worth fixing**: small change, eliminates a latent footgun.
- [ ] **[H1]** Remove the unused `self.fade_ticks` field in `osc.py:106, 120, 130`. **Worth fixing**: trivial cleanup.
- [ ] **[H2]** Convert `Category.master` to a property whose setter routes through `master_interp.set_target(value, 0)` (cancelling any in-flight fade), in `category.py:24-25, 35-48`. Mirrors `MixChannel.offset` behavior. **Worth fixing**: real UX bug.
- [ ] **[Manual: H3]** Decide how interpolated fixture colors should publish to the UI: per-instance direct sends, single-instance broadcast, or via the bound `OSCParam.sync()`. Then implement in `fixtures/basics.py:263-269, 389-402` and `fixtures/spotlights.py:1097-1110`. **Worth fixing** but architectural — needs your call.
- [ ] **[H4]** Round `r_target` / `g_target` / `b_target` / `w_target` getters to `int` in `fixtures/basics.py:200-222, 307-337` and `fixtures/spotlights.py:1023-1053` to preserve `int` return semantics, OR keep a separate integer `target` attribute alongside the float `interp.current`. **Worth fixing**: avoids preset bloat from spurious float drifts. Lean toward the second option for stability.
- [ ] **[H5]** Use `round()` instead of `int()` in `scene.py:177` so `fade_ticks()` better matches requested `fade_ms`. **Worth fixing**: one-line change.
- [ ] **[H6]** Add unit tests for `Interpolator` (snap, multi-tick exactness, retarget) and a regression test for the B1 exception-safety case. **Worth fixing**: trivial primitive, easy to cover, prevents regressions.
- [ ] **[M1]** Add a comment in `osc.py:117-130` documenting that `OSCParam` subclasses overriding `load` must accept `fade_ticks`. Optionally add a CI assertion that walks subclasses. **Worth fixing**: cheap insurance.
- [ ] **[M2]** Default `OSCParam.bind_targets = []` in `osc.py:107` and drop the `is not None` checks. **Worth fixing**: small tidy.
- [ ] **[M3]** Add a one-line invariant note in `Category.set_master` (or explicit `master_interp.current = self.master` resync) in `category.py:35-42`. **Worth fixing**: defends against future regressions.
- [ ] **[M4]** Initialize `self.offset_osc_param: Optional[OSCParam] = None` in `MixChannel.__init__` (`generators/chanmap.py:84-104`) and drop the `hasattr` checks. **Worth fixing**: standard hygiene.
- [ ] **[Manual: M5]** Decide whether `PantiltChannel` should propagate `pending_fade_ticks` into pan/tilt or explicitly opt out of fades. **Lower priority** — current behavior is "moving heads snap" which may be intentional. Document either way.
- [ ] **[M6]** Run `git grep "set_dimming_target("` across the full tree (Python sources, tests, scripts, docs) to confirm no positional callers exist after the `*` keyword-only switch in `fixtures/basics.py:249, 372` and `fixtures/spotlights.py:1080`. **Worth fixing as verification**, not a code change.
- [ ] **[M7]** Add `"steps": "1"` to the `scene/fade_ms` fader at `open-stage-control/layout-config.json:266-273` so the value snaps to integers. **Worth fixing**: cheap UI polish.
- [ ] **[M8]** Add a one-line comment in `generators/mixer.py:494-498` noting that `fade_ticks` is intentionally ignored (patch routing is discrete). **Worth fixing**: helps the next reader.
- [ ] **[M9]** Add a docstring note to `Interpolator.tick` in `util/interpolator.py:26-34` clarifying that the final tick may cover a slightly larger delta than `step` to guarantee exact landing on `target`. **Worth fixing**: trivial.
- [ ] **[L1]** Extract a `_propagate_fade(ticks)` helper in `osc.py:117-130` to deduplicate the set/reset loops. Skip if you take H1 + tidy the whole method together.
- [ ] **[L2]** No action required — flag the dual-source-of-truth pattern for future cleanup (`category.py:24-25`, `chanmap.py:99-100`).
- [ ] **[L3]** Add a one-line comment in `generators/chanmap.py:115-117` explaining the implicit-`ticks=0` `set_target` cancels any in-flight fade. **Worth fixing**: trivial.
- [ ] **[L4]** Add a comment in `fixtures/spotlights.py` near `Spot.color` (~line 95) explaining moving-head colors are intentionally not fade-capable. **Worth fixing**: trivial.
- [ ] **[Manual: L5]** Evaluate whether the `pending_fade_ticks` side-channel is worth replacing with explicit `fade_ticks` parameters on setters / a dedicated `set_with_fade()` method. **Skip unless** the pattern starts spreading to more setters — at current scale the side-channel is acceptable.
- [ ] **[L6]** Add `value = max(0.0, value)` in `SceneManager.set_fade_ms` at `scene.py:167-171`. **Worth fixing**: cheap defensive.
- [ ] **[L7]** Skip — `/scene/fade_ms` chatter on every `sync()` is harmless.
- [ ] **[Manual: L8]** Decide whether `Interpolator.set_target` should reject negative `ticks` or silently treat them as zero. Current behavior is silently zero; documentable but worth a deliberate choice.
- [ ] **[L9]** Pick a convention for slash-in-ID vs explicit `address` for the new `scene/fade_ms` widget at `open-stage-control/layout-config.json:258`. **Skip** unless you're standardising.
- [ ] **[N1]** Standardize on initialized attributes vs `hasattr` checks in `osc.py:123` and `generators/chanmap.py:112, 130`. **Skip** unless touching those files for other reasons.
- [ ] **[N2]** Optionally inline `self.remaining_ticks > 0` instead of going through `self.active` in `Interpolator.tick`. **Skip** — micro-optimization at best.
- [ ] **[N3]** Drop `"address": "auto"` from the `scene_fade_ms_text` textarea in `open-stage-control/layout-config.json:288`. **Skip** — bypassed anyway.
