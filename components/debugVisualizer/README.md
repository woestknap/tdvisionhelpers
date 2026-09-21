# debugVisualizer (Phase 3B)

`debugVisualizer` is a development/debugging helper. It prepares compact,
canonical-coordinate DATs for a TouchDesigner-native overlay network; it does
not process images, alter upstream data, or perform drawing in Python.

## Custom parameters

Create a custom page named **Debug Visualizer** with these OP parameters:

| Label | Internal name | Expected input |
| --- | --- | --- |
| Image TOP | `Imagetop` | Source camera/video TOP |
| Object DAT | `Objectdat` | `smoother/output` |
| Velocity DAT | `Velocitydat` | `velocity/output` |
| Zone State DAT | `Zonestatedat` | `zoneManager/output` |
| Zone Definitions DAT | `Zonedefdat` | Explicit zone-definition Table DAT |

The controller prepares DATs only; `Imagetop` is supplied for the manually
assembled native rendering network and is not read into Python.

## Coordinate convention and inputs

All geometry remains normalized, with origin at bottom-left, X increasing right,
and Y increasing up. `Objectdat` is the one-row `smoother/output` schema;
`Velocitydat` is the corresponding `velocity/output` schema; zone definitions
use `name, x1, y1, x2, y2`; and zone state uses
`zone, inside, entered, exited, source_type, id`.

Object geometry must contain valid finite center and bounding-box coordinates.
The object overlay uses its bbox, center, identity, non-empty class name,
confidence, and raw `depth_raw` when available. `depth_raw` remains untouched:
it is raw relative non-metric YOLO depth.

## Prepared internal DATs

Add Table DATs named `objectData` and `zoneData` inside the component.

`objectData` contains at most one row with this exact header:

```text
source_type
id
class_name
confidence
depth_raw
center_x
center_y
x1
y1
x2
y2
velocity_x
velocity_y
velocity_end_x
velocity_end_y
speed
label
```

The label is `<class_name> #<id>` when `class_name` is non-empty; otherwise it
is `<source_type> #<id>`. Velocity fields stay empty unless the velocity row is
valid and has the same `(source_type, id)` identity as the object.

`zoneData` has one row per valid unique zone definition, in first-valid table
order:

```text
zone
x1
y1
x2
y2
inside
entered
exited
```

Zones remain drawable when zone state is unavailable; their flags default to
zero. Zones may overlap. Malformed rows and reversed bounds are skipped, the
first valid duplicate name wins, and coordinates outside `0..1` are preserved.
Zone state is matched by zone name only. A valid exit state from the previous
object identity is retained rather than rejected.

## Velocity visualization

The controller uses the fixed debug-only scale:

```text
VELOCITY_VISUAL_SCALE = 0.15
end_x = center_x + velocity_x * 0.15
end_y = center_y + velocity_y * 0.15
```

Endpoints are not clamped. The line is an image-space debug cue, not a metric
distance representation. No depth velocity is drawn or calculated.

## Graceful degradation and update behavior

The component is stateless and parses current input DAT contents each Frame End.
It does not extend or recreate events. A missing/malformed object clears only
`objectData`; a missing/malformed velocity removes only velocity fields; a
missing/malformed zone-state DAT leaves valid zones inactive; and a missing or
malformed zone-definition DAT clears only `zoneData`.

## Recommended TouchDesigner-native rendering network

Use one transparent orthographic Render TOP overlay, then Composite it over the
explicit `Imagetop`. This keeps canonical-to-render coordinate conversion at the
rendering boundary and avoids any TOP-to-NumPy pixel round trip.

1. Feed `objectData` and `zoneData` through separate DAT to CHOPs. Use Math
   CHOPs only at this boundary to derive rectangle center/size from `x1/y1/x2/y2`.
2. Create a unit outline rectangle SOP centered at `(0,0)` and instance it in a
   Geometry COMP from `zoneData`; translate/scale with the derived zone CHOP.
   Use `inside`, `entered`, and `exited` channels to drive simple instance color
   choices (inactive, active, enter, exit).
3. Use a second instance of that unit rectangle for the one `objectData` bbox,
   plus a small Circle SOP or point marker at `center_x/center_y`.
4. For velocity, use a unit horizontal Line SOP. Derive the vector
   `velocity_end - center`, its length, and angle with Math/Analyze CHOPs;
   translate the line to the center, rotate it, and scale it to vector length.
   Disable this geometry when `velocity_x` is empty.
5. Render these Geometry COMPs with an orthographic Camera COMP whose image
   plane maps `(0,0)` to lower-left and `(1,1)` to upper-right. Set Render TOP
   resolution to the source Image TOP resolution.
6. Use a Text TOP for the single object label/metrics, with parameter expressions
   reading `objectData`. For TOP-positioned text, convert at this boundary with
   `top_y = 1 - canonical_y`. Use a Replicator COMP driven by `zoneData` to
   create one simple Text TOP per zone name/state label, with the same Y conversion.
7. Composite transparent Render TOP and Text TOP layers over `Imagetop` using
   Composite TOPs set to **Over**. The final Composite TOP is the output TOP.

This intentionally uses plain instanced geometry and Text TOPs: native TD
operators render pixels, while Python only prepares small tables.

## TouchDesigner construction

1. Create a Base COMP named `debugVisualizer`; add Table DATs `objectData` and
   `zoneData`.
2. Add the **Debug Visualizer** parameters above. Typical development paths are
   `/project1/smoother/output`, `/project1/velocity/output`,
   `/project1/zoneManager/output`, and `/project1/zoneManager/zones`.
3. Add an extension Text DAT named `debugVisualizerExt`, set its extension class
   to `DebugVisualizerExt`, and promote it. During development, set its File to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/debugVisualizer/debugVisualizerExt.py
   ```

   Use this Extension Object expression:

   ```python
   me.op('debugVisualizerExt').module.DebugVisualizerExt(me)
   ```

4. Add an Execute DAT using `debugVisualizer_execute_callbacks.py`, enable
   **Frame End**, and use this development File path:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/debugVisualizer/debugVisualizer_execute_callbacks.py
   ```

5. Assemble the native network above and expose its final Composite TOP as the
   visualizer output. Pulse **Re-Init Extensions** after extension changes.

## Runtime visual checklist

- Confirm bbox, center, and labels align to the source TOP without flipping Y.
- Confirm positive X/Y velocity endpoints point right/up and may extend outside
  the image rather than being clamped.
- Confirm mismatched velocity identity removes the vector.
- Confirm overlapping zones all draw, active zones distinguish visually, and
  entered/exited pulses reflect `zoneManager/output` without extension.
- Confirm missing optional DATs remove only their affected overlay.

## Packaging after runtime verification

Embed both final scripts in their Text DATs, disable **Sync to File**, clear
their File fields, retain the embedded code, pulse **Re-Init Extensions**, and
save `tox/debugVisualizer.tox`. Reopen it outside this repository to verify the
component is self-contained before distribution.
