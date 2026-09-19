# Phase 1 design: adapters and depth fusion

This is the smallest proposed architecture based on the local upstream
interfaces documented in [yolo-interface.md](yolo-interface.md) and
[depth-interface.md](depth-interface.md).  It intentionally adds no ML
inference, identity tracker, visualizer, smoothing, or generalized plugin
layer.

## Canonical conventions

- Geometry is normalized: X and Y span 0.0..1.0.
- Canonical origin is bottom-left, with Y increasing upward.  This matches the
  serialized YOLO JSON source convention.
- A canonical record always has: `id`, `class_id`, `class_name`, `confidence`,
  `center_x`, `center_y`, `width`, `height`, `x1`, `y1`, `x2`, `y2`.
- Optional enrichments are: `depth_raw`, `depth_normalized`, `velocity_x`,
  `velocity_y`, `velocity_depth`, `age`, `visible`.
- The canonical initial DAT should use an empty string for unavailable numeric
  enrichment values and `visible` = `0`; it must not substitute a fabricated
  zero depth.  `class_name` is the empty string when no explicit class map is
  configured.
- Depth is relative.  `depth_raw` means the sampled source R value;
  `depth_normalized` is that value mapped to 0..1.  Neither means meters.

## Components

| Component | Single responsibility | Inputs | Outputs |
| --- | --- | --- | --- |
| `yoloData` | Adapt upstream YOLO JSON to canonical detections | Explicit reference/path to the YOLO `predictions` DAT | Canonical detection DAT |
| `depthSampler` | Sample a depth TOP for each canonical detection | Canonical detection DAT; explicit reference/path to Depth Anything output TOP | Per-ID depth DAT, plus optional diagnostic TOP only if needed later |
| `visionFusion` | Attach same-frame depth fields to canonical detections | Canonical detection DAT; per-ID depth DAT | Enriched canonical detection DAT |

The explicit upstream references isolate undocumented component connector
layouts in the adapters.  Downstream helpers consume only canonical DATs.

### `yoloData`

`yoloData` parses the JSON text DAT and chooses `predictions`, `yolo`, or
`yolo_pose` from its message type.  It preserves the upstream `id`.  It maps
`categoryName[0]` to `class_id`; because the source supplies no label map,
`class_name` defaults to `""` unless the user provides a documented mapping.

It converts normal detection `tx`/`ty` from center coordinates to corners.
It treats pose `tx`/`ty` as lower-left coordinates, as documented in the
upstream serializer.  The output is one current-frame canonical row per
visible upstream record.  It does not track, smooth, estimate velocity, or
infer a class name.

Useful minimal parameters: `Source DAT`, `Include Object Detections`, `Include
Pose Detections`, and an optional explicit `Class Map DAT`.

### `depthSampler`

`depthSampler` receives canonical boxes and a depth TOP.  Its initial default
sample is the median of a reduced inner bounding-box ROI, rather than the
center pixel.  It converts canonical normalized corners to the depth TOP's
current pixel dimensions each cook and clips the ROI to valid pixels.

It must have a clearly named `Depth Y Orientation` parameter (`Bottom-left` or
`Top-left`) until the TDDepthAnything output orientation is verified.  The
sampler emits rows keyed by `id` containing `depth_raw`,
`depth_normalized`, `visible`, and a predictable unavailable state.  It does
not invent metric units or decide whether high depth is near/far.

Useful minimal parameters: `Depth TOP`, `ROI Scale` (sensible inner-region
default), `Depth Y Orientation`, and `No Data Value` only if a documented
upstream sentinel becomes necessary.

### `visionFusion`

`visionFusion` joins only current-frame `depthSampler` rows to current-frame
`yoloData` records by `id`.  It copies all canonical detection fields and
appends `depth_raw`, `depth_normalized`, and `visible`; a missing or stale
depth row uses the agreed predictable unavailable representation.  It neither
creates nor changes identity IDs, and it adds no temporal behavior.

Useful minimal parameters: `Detection DAT`, `Depth DAT`, and a `Require Same
Frame` toggle.  If frame metadata is exposed consistently by both adapters,
the default should require matching source frame/sequence; otherwise this
check remains deferred until runtime observation documents reliable metadata.

## Intended flow

```text
yolo.tox predictions DAT ──> yoloData ──> canonical detection DAT ──┐
                                                                      ├─> visionFusion ─> enriched canonical DAT
TDDepthAnything depth TOP ──> depthSampler ─> per-ID depth DAT ──────┘
```

## Runtime prerequisites before implementation

1. Confirm the public connector/operator paths for YOLO `predictions` and
   TDDepthAnything's `script1` output.
2. Confirm both TOPs receive the same camera view with matching orientation,
   crop, and aspect treatment.
3. Establish the Depth Anything output row orientation and numerical
   near/far direction with a known scene.
4. Capture representative YOLO JSON for detection-only, pose-only, and
   combined modes to confirm the exact live DAT text and any component-version
   drift.
