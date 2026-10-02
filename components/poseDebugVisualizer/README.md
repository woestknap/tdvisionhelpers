# poseDebugVisualizer

`poseDebugVisualizer` prepares compact multi-person pose data for a native
TouchDesigner overlay. It consumes the two public outputs from `poseData` and
does not draw pixels, run inference, track, smooth, or associate pose IDs with
object-detection IDs.

It supports zero, one, or many current poses. Canonical pose identity is always
`(source_type, id)`, where `source_type` is `pose`. Duplicate upstream pose IDs
are preserved; they are not deduplicated or renumbered.

## Public parameters

Create a custom page with these parameters:

| Label | Internal name | Type | Purpose |
| --- | --- | --- | --- |
| Image TOP | `Imagetop` | OP | Image over which the native overlay is composited. |
| Poses DAT | `Posesdat` | OP | `poseData/poses`. |
| Keypoints DAT | `Keypointsdat` | OP | `poseData/keypoints`. |
| Show BBox | `Showbbox` | Toggle | Native bbox-geometry visibility control. |
| Show Keypoints | `Showkeypoints` | Toggle | Native keypoint-geometry visibility control. |
| Show Skeleton | `Showskeleton` | Toggle | Native skeleton-geometry visibility control. |
| Show Labels | `Showlabels` | Toggle | Native label-layer visibility control. |
| Min Confidence | `Minconfidence` | Float | Visual-only keypoint threshold; recommended default `0.0`. |

The visibility toggles are consumed by the native rendering network. The
controller does not alter the input `poseData` tables. `Imagetop` is likewise
used by the native network rather than read into Python.

## Expected inputs and coordinates

`Posesdat` must have:

```text
source_type,id,confidence,x1,y1,x2,y2,source_frame,source_seq,video_frame
```

`Keypointsdat` must have:

```text
source_type,id,keypoint_id,keypoint_name,x,y,confidence,source_frame,source_seq,video_frame
```

Coordinates are normalized, origin bottom-left, with X increasing right and Y
increasing up. The component uses only rows whose `source_type` is exactly
`pose` and never associates them with object detections.

## Prepared DATs

Add root-level Table DATs named `poseDataPrepared`, `keypointData`,
`skeletonData`, and `poseLabelReplicas`.

`poseDataPrepared` contains one row per valid pose in input order:

```text
source_type,id,confidence,x1,y1,x2,y2,label
```

`label` is exactly:

```text
pose #<id>
conf <confidence>
```

`keypointData` preserves valid keypoints in input order:

```text
source_type,id,keypoint_id,keypoint_name,x,y,confidence,visible
```

`visible` is `1` when `confidence >= Minconfidence`, otherwise `0`. Low
confidence keypoints remain in this table; the threshold is visualization-only.

`skeletonData` has 16 rows for every valid pose, in locked connection order:

```text
source_type,id,bone_index,start_keypoint_id,end_keypoint_id,x1,y1,x2,y2,visible
```

If either endpoint is missing, that bone row remains present with the missing
endpoint coordinate fields blank and `visible=0`. This stable 16-bones-per-pose
contract keeps native instancing predictable. A bone is `visible=1` only when
both endpoints exist and both meet `Minconfidence`.

`poseLabelReplicas` is the static template DAT for the pose-label Replicator:

```text
name
item1
item2
...
itemN
```

`itemN` maps to `poseDataPrepared` row `N`; the header-only table represents
zero poses. The controller changes this DAT only when the valid pose count
changes. Use it as the Replicator **Template DAT**, rather than the live
`poseDataPrepared` DAT: coordinates and confidence can then update every frame
without needlessly rebuilding Replicator children or swapping Composite TOP
inputs.

## COCO-17 map and skeleton

```text
0 nose             1 left_eye        2 right_eye
3 left_ear         4 right_ear       5 left_shoulder
6 right_shoulder   7 left_elbow      8 right_elbow
9 left_wrist      10 right_wrist    11 left_hip
12 right_hip      13 left_knee      14 right_knee
15 left_ankle     16 right_ankle
```

The skeleton rows use exactly this order:

```text
nose-left_eye
nose-right_eye
left_eye-left_ear
right_eye-right_ear
left_shoulder-right_shoulder
left_shoulder-left_elbow
left_elbow-left_wrist
right_shoulder-right_elbow
right_elbow-right_wrist
left_shoulder-left_hip
right_shoulder-right_hip
left_hip-right_hip
left_hip-left_knee
left_knee-left_ankle
right_hip-right_knee
right_knee-right_ankle
```

## Validation and graceful behavior

Missing/malformed inputs, missing columns, header-only DATs, or malformed rows
produce valid header-only prepared outputs where applicable; stale rows are
cleared every Frame End. Invalid rows do not suppress valid siblings. Missing
image input does not affect table preparation. No tracker is created, and
duplicate pose IDs remain duplicate rows.

For skeleton lookup, the first valid keypoint for a duplicated `(source_type,
id, keypoint_id)` is used. This is the only deterministic interpretation
available from the locked keypoint schema when upstream duplicates a pose ID;
all valid keypoint input rows still remain present in `keypointData`.

## Recommended native TouchDesigner rendering network

Use the prepared DATs with native operators:

1. Convert `poseDataPrepared`, `keypointData`, and `skeletonData` with DAT to
   CHOP operators.
2. Instance a unit rectangle in a Geometry COMP from `poseDataPrepared` for
   bounding boxes; derive center and scale from `x1/y1/x2/y2`. Gate it with
   `Showbbox`.
3. Instance a small Circle SOP or point geometry from `keypointData`, using
   `x/y` and `visible`; gate the layer with `Showkeypoints`.
4. Instance a unit Line SOP from `skeletonData`. Derive line midpoint, length,
   and angle from `x1/y1/x2/y2`; use `visible` to disable missing or
   low-confidence bones and gate the layer with `Showskeleton`.
5. Use a Replicator COMP with `poseLabelReplicas` as its **Template DAT** to
   create one Text TOP label per pose. `itemN` reads `poseDataPrepared` row N.
   Convert canonical Y to TOP pixels at that boundary and use dynamic
   `Imagetop` dimensions; gate the Composite label layer with `Showlabels`.
6. Render geometry with an orthographic Camera mapping `(0,0)` to lower-left
   and `(1,1)` to upper-right. Set the Render TOP resolution from `Imagetop`,
   then Composite Render/Text layers **Over** `Imagetop`.

Do not create one fixed SOP or label operator per person.

## Manual TouchDesigner setup

1. Create Base COMP `poseDebugVisualizer` and add the parameters above.
2. Add Table DATs `poseDataPrepared`, `keypointData`, `skeletonData`, and
   `poseLabelReplicas`.
3. Add Text DAT `poseDebugVisualizerExt` from `poseDebugVisualizerExt.py`, set
   its extension class to `PoseDebugVisualizerExt`, promote it, and use:

   ```python
   me.op('poseDebugVisualizerExt').module.PoseDebugVisualizerExt(me)
   ```

4. Add an Execute DAT from `poseDebugVisualizer_execute_callbacks.py` and
   enable **Frame End**.
5. Point `Posesdat` and `Keypointsdat` at `poseData/poses` and
   `poseData/keypoints`; point `Imagetop` at the source image TOP.
6. Build the native rendering network above. Test zero, one, and many poses,
   low-confidence/missing keypoints, duplicate IDs, and dynamic image size.

## Deliberate exclusions

This component does not modify `poseData`, filter source data, perform object
association, tracking, smoothing, velocity, depth sampling, pose analysis,
body measurements, angles, or inference.
