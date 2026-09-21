# smoother (Phase 2B)

`smoother` applies time-based exponential smoothing to the selected object's
current 2D geometry. It consumes `objectSelector/output` and emits the same
canonical table schema. It does not track objects, smooth depth, calculate
velocity, or modify source metadata.

## Custom parameters

Create a custom page named **Smoother** with these parameters:

| Label | Internal name | Type | Default | Range |
| --- | --- | --- | --- | --- |
| Input DAT | `Inputdat` | OP (DAT) | — | — |
| Smooth Time | `Smoothtime` | Float | `0.15` | `0.0` to `2.0` seconds |

## Input and output contract

Input is the at-most-one-row `objectSelector/output` schema. Output uses this
exact same header and contains at most one row:

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
```

Only `center_x`, `center_y`, `width`, `height`, `x1`, `y1`, `x2`, and `y2`
are smoothed. Every other field comes from the current input row unchanged,
including raw relative `depth_raw`, confidence, identity, and opaque source
metadata. `depth_raw` is not smoothed, clamped, normalized, inverted, or
interpreted as physical distance.

Canonical identity is `(source_type, id)`; an ID alone is not globally unique.

## Smoothing and reset behavior

For a new valid sample of the same identity, the component uses:

```text
alpha = 1 - exp(-dt / Smooth Time)
smoothed = previous + alpha * (current - previous)
```

`dt` is elapsed runtime time since the preceding valid sample for that identity.
`Smooth Time = 0` passes current geometry through immediately. Invalid or
non-positive `dt` also uses current geometry immediately, preventing a clock
discontinuity from freezing output. A large valid `dt` remains stable and
naturally approaches current geometry.

State resets immediately when input is missing, header-only, malformed, has
unusable geometry, or changes canonical identity. The next valid row then
initializes directly from current geometry; interpolation never crosses between
objects or over a target-loss gap.

The component processes every new input sample. It recognizes an exact repeat
of the complete current input row (including opaque source metadata) and does
not advance smoothing twice for that repeat cook. Parameter edits alone do not
advance state; the new Smooth Time applies to the next new sample.

## TouchDesigner construction

1. Create a Base COMP named `smoother`, then add a Table DAT named `output`.
2. Add the **Smoother** custom page and parameters listed above. Set `Inputdat`
   to `objectSelector/output`.
3. Add an extension Text DAT named `smootherExt`, set its extension class to
   `SmootherExt`, and promote it. During development, its File parameter may
   point to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/smoother/smootherExt.py
   ```

   Use this Extension Object expression:

   ```python
   me.op('smootherExt').module.SmootherExt(me)
   ```

4. Add an Execute DAT with `smoother_execute_callbacks.py` as callbacks and
   enable **Frame End**. Its development File parameter may point to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/smoother/smoother_execute_callbacks.py
   ```

5. After changing extension code, pulse **Re-Init Extensions** on the Base
   COMP.

## Packaging after runtime verification

To distribute a self-contained `smoother.tox`, copy the final extension and
Execute DAT code into their internal Text DATs. Disable **Sync to File**, clear
both Text DAT **File** fields, confirm embedded code remains present, then save
the component as `smoother.tox`. Reopen it from a folder without this repository
and confirm it cooks before distribution.
