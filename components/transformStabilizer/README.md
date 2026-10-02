# transformStabilizer

`transformStabilizer` reduces the stepped appearance of lower-cadence pose
measurements without using an EMA-only delay. It consumes
`attachmentTransform/transformData`, applies light alpha-beta position
correction, estimates position velocity, and outputs a short forward prediction
for each current transform identity.

Identity is exactly `(source_type, id, anchor)`. It does not track,
re-identify, associate objects with poses, or retain ghost rows.

## Parameters

Create these parameters on the Base COMP:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Input DAT | `Inputdat` | OP | `attachmentTransform/transformData` |
| Position Alpha | `Positionalpha` | Float | `0.65` |
| Position Beta | `Positionbeta` | Float | `0.08` |
| Scale Alpha | `Scalealpha` | Float | `0.35` |
| Rotation Alpha | `Rotationalpha` | Float | `0.35` |
| Prediction ms | `Predictionms` | Float | `40.0` |
| Max Prediction ms | `Maxpredictionms` | Float | `80.0` |
| Max Gap ms | `Maxgapms` | Float | `250.0` |
| Enabled | `Enabled` | Toggle | On |

Alpha/beta values are logically constrained to `0..1`; negative time values
are constrained to zero. Invalid parameter values use the documented defaults.

## Output

Add a root Table DAT named `stabilizedTransformData`. Its schema is unchanged
from `attachmentTransform`:

```text
source_type,id,anchor,x,y,scale,rotation,confidence,visible,source_frame,source_seq,video_frame
```

Input row order, confidence, visibility, and source metadata are preserved.
Coordinates remain normalized in the bottom-left convention. Rotation output is
normalized to `[-180, 180)` degrees.

## Filter and prediction behavior

For a new measurement, the state initializes directly from its x/y, scale, and
rotation. Later measurements use an alpha-beta position update: the previous
filtered point is predicted with velocity, position is corrected by
`Positionalpha`, and velocity is corrected by `Positionbeta / dt` when `dt` is
safe. Scale uses `Scalealpha` only and is never velocity-predicted.

Each output uses current elapsed extrapolation plus:

```text
min(Predictionms, Maxpredictionms) / 1000
```

seconds of forward prediction. That predicted value is never stored back into
the filter state, so it cannot recursively compound every TouchDesigner frame.

Repeated TouchDesigner cooks with unchanged upstream metadata and transform
values have the same measurement signature, so they do not apply repeated
measurement correction. They only evaluate the existing velocity prediction.
Changing frame/sequence/video metadata or transform values creates a new
measurement.

Rotation uses shortest-angle interpolation: `179` to `-179` is treated as a
roughly two-degree change, not a 358-degree turn. There is no rotation or scale
velocity prediction in v1.

## Visibility, disappearance, and A/B testing

An input row with `visible=0` is output with `visible=0` and clears its filter
state; prediction never draws a lost pose. Missing/malformed numeric
measurements are likewise non-visible and do not fabricate coordinates. Absent
identities are removed immediately. If a fresh measurement arrives after a gap
larger than `Maxgapms`, its velocity is reset and it initializes directly.

With `Enabled` off, every accepted input row is passed through exactly without
smoothing or prediction, and all state is cleared. This supports an immediate
A/B comparison.

Missing, header-only, or malformed input clears the output to its header.
Malformed siblings do not prevent valid rows from processing. Numeric zero is
valid.

## Manual TouchDesigner setup

1. Create Base COMP `transformStabilizer` and add the parameters above.
2. Add root Table DAT `stabilizedTransformData`.
3. Add Text DAT `transformStabilizerExt` from `transformStabilizerExt.py`, set
   its extension class to `TransformStabilizerExt`, promote it, and use:

   ```python
   me.op('transformStabilizerExt').module.TransformStabilizerExt(me)
   ```

4. Add an Execute DAT using `transformStabilizer_execute_callbacks.py`; enable
   **Frame End**.
5. Point `Inputdat` to `attachmentTransform/transformData`. For A/B testing,
   point `graphicAttachment/Transformdat` at this output, then toggle `Enabled`
   while observing moving poses. Test repeated source frames, changing frame
   metadata, a 179/-179 rotation crossing, invisibility, disappearance, and a
   stall longer than `Maxgapms`.

## Deliberate exclusions

No Kalman/NumPy dependency, acceleration model, scale/rotation velocity,
tracking, object-pose association, depth, rendering, effects, or persistence
across tracker-ID changes is included.
