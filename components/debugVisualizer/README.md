# debugVisualizer (Phase 5)

`debugVisualizer` is a development/debugging helper for rendering zero, one,
or many canonical objects and aggregated zones over an image. It prepares
compact canonical-coordinate DATs for a TouchDesigner-native overlay network;
it does not process images, alter upstream data, or perform drawing in Python.

The intended multi-object inputs are `smoother/output`, `velocity/output`,
`zoneManager/output`, and the explicit zone-definition DAT from this pipeline:

```text
visionFusion → classFilter → smoother ──→ velocity
                                  └─────→ zoneManager
```

The controller prepares tables only. The native TouchDesigner rendering network
must consume multiple `objectData` rows through efficient instancing or dynamic
rendering; Python does not create per-object render operators.

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
and Y increasing up. `Objectdat` is the zero/one/many-row `smoother/output`
schema; `Velocitydat` is the corresponding multi-row `velocity/output` schema; zone definitions
use `name, x1, y1, x2, y2`; and zone state uses
`zone, inside, entered, exited, source_type, id`.

Object geometry must contain valid finite center and bounding-box coordinates.
The object overlay uses its bbox, center, identity, non-empty class name,
confidence, and raw `depth_raw` when available. `depth_raw` remains untouched:
it is raw relative non-metric YOLO depth.

## Prepared internal DATs

Add Table DATs named `objectData` and `zoneData` inside the component.

`objectData` contains one row for every valid current object, preserving
`Objectdat` row order, with this exact header:

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
is `<source_type> #<id>`. Velocity fields stay empty unless a valid velocity
row has the same `(source_type, id)` identity as the object. The first valid
velocity row for a duplicate identity wins deterministically; extra velocity
identities are ignored. This debug join does not require frame-metadata equality.

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
`zoneManager/output` may contain several rows for the same zone, one per
identity. `zoneData` intentionally remains zone-level: `inside`, `entered`, and
`exited` each equal 1 when **any** valid identity row for that zone has the
respective flag. Identified zone-state rows take precedence over blank-identity
legacy rows for the same zone, even when all identified flags are zero.

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
It does not extend or recreate events, track identities, or create per-object
rendering operators. A missing/malformed object clears only `objectData`; a
missing/malformed velocity removes only velocity fields; a missing/malformed
zone-state DAT leaves valid zones inactive; and a missing or malformed
zone-definition DAT clears only `zoneData`.

## Finalized TouchDesigner-native rendering network

Use one transparent orthographic Render TOP overlay, then Composite it over the
explicit `Imagetop`. This keeps canonical-to-render coordinate conversion at the
rendering boundary and avoids any TOP-to-NumPy pixel round trip.

### Object geometry

`objectCHOP` receives `objectData` and supplies the instanced geometry path:

- `bboxTransform` drives `bboxUnit` in `bboxGeometry`.
- The same object instance data drives `centerUnit` in `centerGeometry`.
- `velocityTransform` drives `velocityUnit` in `velocityGeometry`.

This is intentionally a zero/one/many-object path. The controller does not
construct geometry, and obsolete single-object render operators (`bboxSOP`,
`bboxwire`, `centerSOP`, and `velocitySOP`) must not be reintroduced.

Velocity uses the prepared `velocity_end - center` vector. Its endpoint uses
the fixed visualization-only scale `VELOCITY_VISUAL_SCALE = 0.15`; it is not a
physical prediction. Render the Geometry COMPs with an orthographic Camera
whose image plane maps `(0,0)` to lower-left and `(1,1)` to upper-right. Set
the Render TOP resolution to `sourceImage`.

### Object labels

`objectLabelReplicator`, driven by `objectData`, creates an
`objectLabelTemplate` replica for every current row. Replica order is part of
the maintained contract: `item1` shows `objectData` row 1, `item2` row 2, and
`itemN` row N. Each replica contributes `out1` to `objectLabelsComposite`.

Each replica's `text1` displays:

```text
<class_name> #<id>
conf <confidence>
depth <depth_raw>
speed <speed>
```

Its TOP matches `sourceImage` resolution. With Horizontal Align **Left** and
Vertical Align **Top**, position `text1` using the runtime-verified conversion:

```text
positionX = x1 * sourceImage.width + 8
positionY = -(1.0 - y2) * sourceImage.height - 8
```

`objectLabelsComposite` includes two permanent transparent Constant TOPs so it
remains valid when the replicator has zero object replicas. `objectLabel` and
`labelComposite` are obsolete single-object nodes and must not be reintroduced.

### Zones

The existing zone visualization consumes `zoneData`. `zoneData` is aggregated
per zone with ANY semantics for `inside`, `entered`, and `exited`. The existing
`zoneLabelReplicator` can create one label per named zone; its callback uses the
same pixel-position conversion above with the zone's `x1` and `y2`.

Composite transparent Render TOP and Text TOP layers over `Imagetop` using
**Over**. The final Composite TOP is the visualizer output TOP.

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

5. Assemble the finalized native network: `objectCHOP`, `bboxTransform`,
   `bboxUnit`, `bboxGeometry`, `centerUnit`, `centerGeometry`,
   `velocityTransform`, `velocityUnit`, `velocityGeometry`,
   `objectLabelTemplate`, `objectLabelReplicator`, and
   `objectLabelsComposite`. Retain the existing zone visualization and
   `zoneLabelReplicator`. Expose the final Composite TOP as the visualizer
   output. Pulse **Re-Init Extensions** after extension changes.

`objectSelector` remains compatible: its one-row output produces one object
instance and an `item1` label replica.

## Runtime visual checklist

- Confirm zero, one, and many objects retain `objectData` input order in the
  bbox, center, velocity, and `itemN` label paths.
- Confirm bbox, center, and labels align to the source TOP without flipping Y;
  labels use the documented `x1` / `y2` pixel conversion.
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
