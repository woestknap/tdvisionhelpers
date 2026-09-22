# velocity (Phase 2C)

`velocity` calculates current 2D image-space velocity for zero, one, or many
objects supplied by `smoother/output`. It preserves every valid smoother row in
input order and appends three velocity fields. It remains compatible with the
original one-row `objectSelector → smoother → velocity` workflow. It does not
track objects, smooth values, predict motion, calculate acceleration, or
calculate depth velocity.

Typical multi-object placement is:

```text
visionFusion
    ↓
classFilter
    ↓
smoother
    ↓
velocity
```

## Custom parameters

Create a custom page named **Velocity** with one parameter:

| Label | Internal name | Type |
| --- | --- | --- |
| Input DAT | `Inputdat` | OP (DAT) |

Set `Inputdat` to `smoother/output`.

## Input and output contract

The input is the canonical `smoother/output` schema with zero, one, or many
valid rows. Output preserves all original input fields as their current DAT text
and appends exactly these fields:

```text
source_type
id
class_id
class_name
confidence
center_x
center_y
width
height
x1
y1
x2
y2
depth_raw
source_frame
source_seq
video_frame
velocity_x
velocity_y
speed
```

`velocity_x` and `velocity_y` are normalized image-coordinate units per second.
The canonical image origin is bottom-left: positive X means rightward movement,
negative X leftward; positive Y means upward movement, negative Y downward.
`speed` is non-negative and uses the same normalized-units-per-second scale.
These are image-space values, not pixel, camera-space, world-space, or metric
velocities.

`depth_raw` passes through unchanged. It remains raw relative, non-metric YOLO
depth; no depth/Z velocity is calculated. Source metadata also passes through
unchanged and is never used as elapsed time.

## Calculation, identity, and reset behavior

For consecutive valid samples with the same canonical identity
`(source_type, id)`:

```text
velocity_x = (center_x_current - center_x_previous) / dt
velocity_y = (center_y_current - center_y_previous) / dt
speed = sqrt(velocity_x^2 + velocity_y^2)
```

The first valid sample for each identity outputs all three velocity fields as
`0`. State is independent for every canonical identity `(source_type, id)`:
each identity stores its own prior center, full-row signature, sample time, and
last velocity. Velocity is never calculated between identities.

If an identity is absent from the current valid input update, its state is
removed immediately. Its later reappearance starts as a fresh acquisition with
zero velocity. Missing, header-only, or schema-malformed input clears all state
and produces header-only output. A row with invalid center coordinates is
skipped without affecting other identities, and its prior state is removed as
absent.

The component uses TouchDesigner `absTime.seconds` as its runtime clock, with
`time.monotonic()` only as a pure-Python fallback. It does not use source frame
metadata as time. If `dt` is non-finite or non-positive, it safely outputs zero
velocity and stores the current center/time as a fresh baseline. A large valid
`dt` is calculated normally; no prediction or timeout behavior is applied.

An exact repeat of each identity's full current input row is deduplicated, so
repeat cooks do not advance that identity's baseline or affect other identities.
A later row with changed source metadata is accepted even when its center is
identical, producing zero instantaneous velocity for that interval.

## TouchDesigner construction

1. Create a Base COMP named `velocity` and add a Table DAT named `output`.
2. Add the **Velocity** custom page and `Inputdat` OP parameter. Set it to
   `smoother/output`; both the legacy one-row and current multi-row outputs are
   supported.
3. Add an extension Text DAT named `velocityExt`, set its extension class to
   `VelocityExt`, and promote it. During development, set its File parameter to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/velocity/velocityExt.py
   ```

   Use this Extension Object expression:

   ```python
   me.op('velocityExt').module.VelocityExt(me)
   ```

4. Add an Execute DAT with `velocity_execute_callbacks.py` as callbacks and
   enable **Frame End**. Its development File parameter may point to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/velocity/velocity_execute_callbacks.py
   ```

5. After changing extension code, pulse **Re-Init Extensions** on the Base
   COMP.

## Packaging after runtime verification

To distribute a self-contained `velocity.tox`, copy the final extension and
Execute DAT code into their internal Text DATs. Disable **Sync to File**, clear
both Text DAT **File** fields, confirm embedded code remains present, then save
the component as `velocity.tox`. Reopen it from a folder without this repository
and confirm it cooks before distribution.
