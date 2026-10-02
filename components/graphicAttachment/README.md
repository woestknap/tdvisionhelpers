# graphicAttachment

`graphicAttachment` prepares multi-person display transforms for one supplied
graphic TOP. It consumes `attachmentTransform/transformData`; it does not
interpret poses, track identities, select graphics, or render pixels in Python.

Each valid transform row becomes one `graphicTransformData` row in the same
order. Identity is preserved as `(source_type, id)`; duplicate IDs are not
deduplicated.

## Public parameters

Create these Base COMP parameters:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Image TOP | `Imagetop` | OP | — |
| Graphic TOP | `Graphictop` | OP | — |
| Transform DAT | `Transformdat` | OP | `attachmentTransform/transformData` |
| Scale Multiplier | `Scalemultiplier` | Float | `1.0` |
| Rotation Offset | `Rotationoffset` | Float, degrees | `0.0` |
| X Offset | `Xoffset` | Float, normalized | `0.0` |
| Y Offset | `Yoffset` | Float, normalized | `0.0` |
| Opacity | `Opacity` | Float | `1.0` |
| Show Graphic | `Showgraphic` | Toggle | On |

`Opacity` is logically clamped to `0..1`. Missing image or graphic TOPs do not
stop data preparation; they only prevent the future native visual network from
rendering until those inputs are supplied.

## Prepared data

Add a root Table DAT named `graphicTransformData`. It always has this exact
header:

```text
source_type,id,anchor,x,y,scale,rotation,opacity,visible,source_frame,source_seq,video_frame
```

Coordinates remain normalized with origin bottom-left, X right, Y up. For every
valid transform row:

```text
x        = input_x + Xoffset
y        = input_y + Yoffset
scale    = input_scale * Scalemultiplier
rotation = input_rotation + Rotationoffset
opacity  = clamp(Opacity, 0, 1)
```

Rotation remains degrees; positive is counter-clockwise and zero points toward
+X. Scale remains normalized image-space scale. In particular, point-mode
transforms from `attachmentTransform` have scale `1.0`; use a smaller
`Scalemultiplier` when that is visually appropriate. This component never
infers point versus segment mode.

`visible` is `1` only when source `visible` equals `1`, `Showgraphic` is on,
and `x`, `y`, `scale`, `rotation`, and `confidence` are all finite. It never
drops a row merely because `visible=0`.

When individual numeric transform fields are malformed, available fields are
still transformed and unavailable fields are blank; the row is non-visible.
This preserves usable metadata without fabricating a transform. Numeric zero is
valid. Missing/header-only/malformed `Transformdat` produces a header-only
output and clears stale rows.

## Recommended native TouchDesigner network

1. Use Select TOPs to bring `Imagetop` and `Graphictop` into the component.
2. Convert `graphicTransformData` with DAT to CHOP (or a Script CHOP).
3. Create one unit Rectangle SOP/quad and one Geometry COMP. Instance it from
   the CHOP: position from `x/y`, rotation from `rotation`, scale from `scale`,
   and enable/visibility from `visible`.
4. Apply a texture/material fed by `Graphictop`. Keep `opacity` available as an
   instance channel. Basic material paths may not support per-instance opacity
   directly; retain the channel rather than adding shader complexity here.
5. Render with an orthographic camera using normalized bottom-left coordinates,
   set Render TOP resolution dynamically from `Imagetop`, Composite it **Over**
   the image, and expose an Out TOP.

This supports zero, one, or many graphic instances without fixed person counts
or one Geometry COMP per person.

## Deliberate exclusions

No random/per-person graphic selection, animation, tracking, smoothing, depth
occlusion, object-pose association, face landmarks, FM effects, shaders, masks,
segmentation, collision avoidance, or persistence across tracker changes is
implemented.

## Manual TouchDesigner setup

1. Create Base COMP `graphicAttachment` and add the parameters above.
2. Add Table DAT `graphicTransformData`.
3. Add Text DAT `graphicAttachmentExt` from `graphicAttachmentExt.py`, set its
   extension class to `GraphicAttachmentExt`, promote it, and use:

   ```python
   me.op('graphicAttachmentExt').module.GraphicAttachmentExt(me)
   ```

4. Add an Execute DAT using `graphicAttachment_execute_callbacks.py`; enable
   **Frame End**.
5. Point `Transformdat` at `attachmentTransform/transformData`, choose image
   and graphic TOPs, then construct the native network above. Test offsets,
   scale, rotation, opacity clamping, source visibility, Show Graphic, duplicate
   IDs, malformed values, and zero/many transform rows.
