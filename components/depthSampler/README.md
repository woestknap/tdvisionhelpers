# depthSampler (Phase 1B)

`depthSampler` reads current canonical object detections and a spatially
aligned TDDepthAnything TOP, then outputs one relative depth value per valid
object. It does not perform fusion, tracking, smoothing, metric conversion, or
temporal processing.

## Build the component in TouchDesigner

1. Create a Base COMP named `depthSampler` and add a Table DAT named `output`.
2. Add custom OP parameters to the Base COMP:
   - `Detections` (label: **Detections**) — point to `yoloData/output`.
   - `Depthtop` (label: **Depth TOP**) — point to the TDDepthAnything depth
     TOP driven by the same synced frame as YOLO.
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
visual flip. This matches the verified aligned yolo-touchdesigner Synced Frame
and TDDepthAnything runtime setup.

Runtime verification found that TDDepthAnything `script1.numpyArray()` returns
`float32` arrays in `(height, width, 4)` layout; the observed shape was
`(720, 1280, 4)` and range was 0.0..1.0. The observed resolution is not
required or hard-coded. Relative depth is R/channel 0, with sample pixels in
the form `[depth, 0, 0, 0]`. The sampler consumes this normalized float data
directly. `depth_value` is clamped to 0..1: runtime samples were approximately
0.1 for a farther object and 0.9 for a nearer one, confirming 0 is
farther/lower relative depth and 1 is nearer/higher relative depth. It is
never metric distance.

The depth TOP is read through `numpyArray()` once per update, only after at
least one valid detection is found. Missing inputs, invalid rows, empty ROIs,
or no detections produce a valid header-only output DAT. Runtime testing
confirmed that `depth_value` updates continuously and that yoloData detections
are spatially aligned with the TDDepthAnything map.

## Output schema

```text
source_type, id, depth_value, source_frame, source_seq, video_frame
```

Identity and frame metadata are copied directly from the detection row.
