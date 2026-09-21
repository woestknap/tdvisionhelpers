# visionFusion (Phase 1C)

`visionFusion` joins current canonical yoloData object rows with current
depthSampler rows. It does not sample a TOP, track objects, smooth data, or
transform depth values.

## Build the component in TouchDesigner

1. Create a Base COMP named `visionFusion` and add a Table DAT named `output`.
2. Add custom OP parameters to the Base COMP:
   - `Detections` (label: **Detections**) — DAT; point to `yoloData/output`.
   - `Depth` (label: **Depth**) — DAT; point to `depthSampler/output`.
3. Add `visionFusionExt.py` as an extension DAT, set its extension class to
   `VisionFusionExt`, and promote it. For an external development file, use:

   ```python
   me.op('visionFusionExt').module.VisionFusionExt(me)
   ```

4. Add an Execute DAT with `visionFusion_execute_callbacks.py` as callbacks,
   then enable **Frame End**.

Current development-project routing is:

```text
yoloData/output     -> visionFusion.Detections
depthSampler/output -> visionFusion.Depth
```

`depthSampler.Depthtop` is configured separately with the public YOLO Depth
TOP (currently observed at `/project1/yolo/depth`; do not hard-code that path).

## Join and frame policy

The identity key is `(source_type, id)`. Depth additionally requires exact,
non-empty equality of `source_frame`, `source_seq`, and `video_frame`. This
prevents depth from a different source frame being attached to a newer
detection. Metadata is compared and copied as DAT cell text: values such as
`4294967295`, `0`, and floating-point video-frame values are not interpreted,
rounded, or repaired.

An object detection always remains in the output. If no single valid
frame-compatible depth row exists, `depth_raw` is empty. Duplicate matching
depth rows are treated as ambiguous and also leave `depth_raw` empty.

`depth_raw` is copied without normalization, clamping, inversion, or unit
conversion. It is relative/non-metric; lower observed values are nearer and
higher observed values are farther.

The extension compares each input DAT's text each Frame End, so unchanged
inputs do not rebuild the output. It does not rely on DAT cook counts.

## Output schema

```text
source_type, id, class_id, class_name, confidence, center_x, center_y,
width, height, x1, y1, x2, y2, depth_raw, source_frame, source_seq, video_frame
```
