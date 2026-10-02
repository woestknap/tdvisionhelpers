# attachmentTransform

`attachmentTransform` converts current `poseData` keypoints into one normalized
2D transform per pose. It prepares data only: downstream networks can attach
graphics or effects independently to each pose without this component rendering
anything.

It never associates pose IDs with object-detection IDs. Identity is strictly
`(source_type, id)` and `source_type` is expected to be `pose`.

## Public parameters

Create these parameters on the Base COMP:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Poses DAT | `Posesdat` | OP | `poseData/poses` |
| Keypoints DAT | `Keypointsdat` | OP | `poseData/keypoints` |
| Mode | `Mode` | Menu | `point` |
| Point | `Point` | Menu/String | `nose` |
| Point A | `Pointa` | Menu/String | `left_shoulder` |
| Point B | `Pointb` | Menu/String | `right_shoulder` |
| Scale Mode | `Scalemode` | Menu | `fixed` |
| Min Confidence | `Minconfidence` | Float | `0.25` |

`Mode` options are `point` and `segment`. Valid keypoint names are:

```text
nose, left_eye, right_eye, left_ear, right_ear,
left_shoulder, right_shoulder, left_elbow, right_elbow,
left_wrist, right_wrist, left_hip, right_hip, left_knee,
right_knee, left_ankle, right_ankle
```

## Output

Add a root Table DAT named `transformData`. It always contains this exact
header:

```text
source_type,id,anchor,x,y,scale,rotation,confidence,visible,source_frame,source_seq,video_frame
```

There is one row per valid `Posesdat` row, in input order. Pose identity and
frame metadata are copied unchanged from that pose row. Missing/header-only or
malformed required inputs produce a header-only table, clearing stale rows.

Coordinates remain normalized with a bottom-left origin, X right, and Y up.

## Point mode

With `Mode = point`, `Point` selects a keypoint. A valid selected point writes:

```text
anchor = Point
x, y = selected keypoint x, y
rotation = 0.0
confidence = selected keypoint confidence
```

`Scalemode` controls point-mode scale only:

| Scale mode | Point-mode scale |
| --- | --- |
| `fixed` | `1.0` (the backward-compatible default) |
| `bbox_width` | `max(0, x2 - x1)` from the matching pose bbox |
| `bbox_height` | `max(0, y2 - y1)` from the matching pose bbox |
| `bbox_size` | `sqrt(width * height)` from the matching pose bbox |

`bbox_size` provides approximate image-space perspective/distance scaling: a
smaller detected person produces a smaller scale. It remains normalized and is
not metric distance. Bbox matching uses `(source_type, id)`, never row number.
If a non-fixed mode has no valid matching bbox, the pose row remains with
`scale=0` and `visible=0`; it never silently falls back to `1.0`.

`visible` is `1` only when its confidence is at least `Minconfidence`. A
low-confidence but numerically valid point still retains its transform values
with `visible=0`. A missing/malformed selected point leaves transform fields
blank and writes `visible=0`; the pose row remains.

Examples: select `nose` to follow a head point, or `left_wrist` to attach an
effect to that wrist.

## Segment mode

With `Mode = segment`, `Pointa` and `Pointb` define the anchor:

```text
anchor = <pointa>_<pointb>
x, y = midpoint of A and B
scale = normalized Euclidean distance from A to B
rotation = degrees(atan2(By - Ay, Bx - Ax))
confidence = min(A confidence, B confidence)
```

`rotation` is degrees: 0 points toward +X and positive values rotate
counter-clockwise in canonical bottom-left coordinates. Y is not inverted.
`scale` is normalized image-space distance, not pixels or physical distance,
and is not normalized again.

Both points must be valid and meet `Minconfidence` for `visible=1`. If either
is low-confidence but valid, the transform remains computed with `visible=0`.
If either is missing/malformed, transform fields are blank and `visible=0`.
`Scalemode` does not affect segment mode.

Examples: `left_shoulder -> right_shoulder` gives a shoulder-width/rotation
transform; `left_eye -> right_eye` gives an eye-line transform.

## Matching, validation, and limitations

`Minconfidence` controls only `visible`; it never removes low-confidence pose
rows. Numeric zero coordinates and confidence are valid. Invalid pose rows,
invalid keypoint rows, unknown modes, and unknown point names fail gracefully.

Keypoints are matched by `(source_type, id, keypoint_name)`. If duplicate pose
IDs occur in one frame, the locked keypoints schema cannot distinguish those
occurrences. The first valid matching keypoint is deliberately used for every
matching duplicate pose row; IDs are never rewritten or deduplicated.

The component does not render, composite graphics, smooth, track, sample depth,
perform object-pose association, select automatic anchors, derive body metrics,
create 3D/perspective transforms, use physical scale, calculate velocity, or
create per-person random effects.

## Manual TouchDesigner setup

1. Create a Base COMP named `attachmentTransform`.
2. Add the parameters above, including the `Scalemode` menu (`fixed`,
   `bbox_width`, `bbox_height`, `bbox_size`), and a root Table DAT named
   `transformData`.
3. Add a Text DAT named `attachmentTransformExt` from
   `attachmentTransformExt.py`, set its extension class to
   `AttachmentTransformExt`, promote it, and use:

   ```python
   me.op('attachmentTransformExt').module.AttachmentTransformExt(me)
   ```

4. Add an Execute DAT using `attachmentTransform_execute_callbacks.py` and
   enable **Frame End**.
5. Point `Posesdat` and `Keypointsdat` at `poseData/poses` and
   `poseData/keypoints`. Test `nose`, `left_wrist`, shoulder and eye segments,
   low/missing keypoints, duplicate IDs, and zero-coordinate inputs.
