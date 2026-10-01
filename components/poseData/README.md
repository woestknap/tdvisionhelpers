# poseData (Phase 6)

`poseData` adapts only the `yolo_pose` array from a configured
yolo-touchdesigner predictions DAT. It produces canonical pose bounding boxes
and COCO-17 keypoint rows. It never associates `yolo_pose` records with the
upstream `yolo` object-detection array.

## TouchDesigner setup

1. Create a Base COMP named `poseData`.
2. Add a custom OP parameter named `Source` (label: **Source DAT**) and point
   it to the upstream predictions DAT.
3. Add Table DATs named `poses` and `keypoints` at the component root.
4. Add `poseDataExt.py` as a Text DAT named `poseDataExt`, set its extension
   class to `PoseDataExt`, and promote the extension. During development the
   Text DAT may reference this source file. Use this Extension Object expression:

   ```python
   me.op('poseDataExt').module.PoseDataExt(me)
   ```

5. Add an Execute DAT using `poseData_execute_callbacks.py`. Enable **Frame
   End**; its callback calls `parent().Update()` after the upstream source has
   cooked.

## Public output DATs

`poses` always has this exact header:

```text
source_type,id,confidence,x1,y1,x2,y2,source_frame,source_seq,video_frame
```

It has one row per valid upstream pose record. `source_type` is always `pose`.
`id` is copied unchanged from the upstream pose tracker. Object and pose
trackers have independent namespaces, so canonical pose identity is
`(source_type, id)` and an object ID must never be associated with the same
numeric pose ID.

`keypoints` always has this exact header:

```text
source_type,id,keypoint_id,keypoint_name,x,y,confidence,source_frame,source_seq,video_frame
```

It has one row per valid keypoint. Rows follow upstream pose order, then
upstream keypoint/index order within each pose. A complete two-person input
therefore produces two `poses` rows and 34 contiguous `keypoints` rows: the
first person's 17 rows followed by the second person's 17 rows.

## Coordinates and keypoints

All output coordinates use TDVisionHelpers' normalized bottom-left convention:
X increases right and Y increases up. Upstream `yolo_pose` already supplies
`tx`/`ty` as the lower-left bounding-box coordinate, so the adapter writes:

```text
x1 = tx
y1 = ty
x2 = tx + width
y2 = ty + height
```

It does not apply the center-based conversion used by `yoloData`, clamp values,
or invert Y. Keypoint `x` and `y` values are preserved directly.

The public keypoint map is COCO-17:

```text
0 nose             1 left_eye        2 right_eye
3 left_ear         4 right_ear       5 left_shoulder
6 right_shoulder   7 left_elbow      8 right_elbow
9 left_wrist      10 right_wrist    11 left_hip
12 right_hip      13 left_knee      14 right_knee
15 left_ankle     16 right_ankle
```

Only indices 0 through 16 are emitted. Extra upstream keypoints are ignored;
missing keypoints are not synthesized.

## Validation and metadata behavior

A pose requires a dictionary with an ID plus finite numeric `tx`, `ty`,
`width`, `height`, and `score`. An invalid pose is entirely skipped, including
its keypoints. A keypoint requires finite numeric `x`, `y`, and `score`; an
invalid keypoint alone is skipped without affecting sibling keypoints or poses.
Numeric zero is valid, and no confidence threshold is applied: low values such
as `0.02` and `0.0` are preserved.

The adapter copies top-level `frame`, `seq`, and `videoFrame` to
`source_frame`, `source_seq`, and `video_frame` without reinterpretation. If a
metadata field is absent, the corresponding output field is empty; valid zero
values remain zero.

Both tables become header-only for an unset/unavailable source, empty text,
malformed JSON, a non-object JSON root, missing/wrong-type `yolo_pose`, or an
empty pose list. This clears stale output. The source DAT text—not only its
cook count—is compared each Frame End. Losing a source resets the cached source
state, so restoring the same previous JSON is processed again.

## Deliberate exclusions

`poseData` does not process `yolo[]`, associate objects with poses, filter by
confidence, track, smooth, sample depth, interpolate keypoints, synthesize
missing keypoints, visualize, calculate body measurements/angles, or calculate
velocity.
