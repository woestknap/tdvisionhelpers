# depthSampler (Phase 1B)

`depthSampler` reads current canonical object detections and the spatially
aligned public YOLO Depth TOP, then outputs one raw relative-depth sample per
valid object. It does not perform fusion, tracking, smoothing, metric
conversion, normalization, or temporal processing.

## Build the component in TouchDesigner

1. Create a Base COMP named `depthSampler` and add a Table DAT named `output`.
2. Add custom OP parameters to the Base COMP:
   - `Detections` (label: **Detections**) — point to `yoloData/output`.
   - `Depthtop` (label: **Depth TOP**) — point to the public YOLO Depth TOP
     driven by the same synced frame as YOLO. Do not hard-code its path.
3. Add `depthSamplerExt.py` as an extension DAT, set its extension class to
   `DepthSamplerExt`, and promote it. For an external development file, use:

   ```python
   me.op('depthSamplerExt').module.DepthSamplerExt(me)
   ```

4. Add an Execute DAT with `depthSampler_execute_callbacks.py` as its
   callbacks, then enable **Frame End**.

## Sampling behavior

The sampler processes only canonical rows where `source_type` is `object`.
For each valid normalized box, it takes the centered inner 50% width by 50%
height ROI and returns the median of its finite R-channel samples. The fixed
`INNER_ROI_SCALE = 0.5` class constant is the future parameter seam; no custom
parameter has been added yet.

Canonical coordinates use a bottom-left origin. NumPy rows are addressed from
the top, so the sampler maps ROI Y with `1 - y` and does not apply an extra
visual flip. This matches the verified spatial alignment of yoloData
detections and the public YOLO Depth TOP.

Runtime observation of the public YOLO Depth TOP found `float32` arrays in
`(height, width, 4)` layout; the observed shape was `(720, 1280, 4)`, but
resolution is not required or hard-coded. Depth is read from R/channel 0.
The RGB channels appear to contain the depth representation and alpha is 1.
Observed full-frame values exceeded 1.0 (approximately 0.555 to 1.328 in one
frame), so the sampler preserves the median raw value without normalization or
clamping. Lower raw values were nearer and higher raw values were farther in a
movement test (roughly 0.68 near to 2.37 far). These are relative,
non-metric observations; they do not imply any physical-distance conversion.

The depth TOP is read through `numpyArray()` once per update, only after at
least one valid detection is found. Missing inputs, invalid rows, empty ROIs,
or no detections produce a valid header-only output DAT.

## Output schema

```text
source_type, id, depth_raw, source_frame, source_seq, video_frame
```

Identity and frame metadata are copied directly from the detection row.
