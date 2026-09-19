# TDDepthAnything interface reconnaissance

Upstream inspected: `external/TDDepthAnything` at commit
`3e8abb45afda23dde0e90c56dc44caad2820b39b`.

This is an interface record, not a validation of model output.  The source
uses a named internal TOP and Script TOP, while the `.tox` connector layout
must be checked in TouchDesigner.

## VERIFIED FROM TOUCHDESIGNER RUNTIME

- TDDepthAnything was fed from yolo-touchdesigner `output4` / **Synced Frame**.
- Its depth output was spatially aligned with that synced frame. No horizontal
  or vertical flip was observed.
- Nearer objects produced higher, warmer/red depth values. Farther areas
  produced lower, cooler/blue values.
- `script1.numpyArray()` returned `float32` depth arrays with observed shape
  `(720, 1280, 4)` and range `0.0..1.0`. Relative depth is channel 0 / R;
  sampled pixels had the form `[depth, 0, 0, 0]`.
- The observed 1280 x 720 resolution is a runtime observation only, not a
  required or hard-coded resolution.
- yoloData detections and the TDDepthAnything depth map were spatially aligned
  in runtime testing.
- depthSampler successfully consumed the normalized `float32` representation
  and its `depth_value` updated continuously. Runtime samples were roughly
  0.1 for a farther object and 0.9 for a nearer object, confirming canonical
  `0 = farther` and `1 = nearer`.
- The output remains relative depth, not metric distance. TDDepthAnything
  performs per-frame min/max normalization, so a value is not a stable
  physical distance across frames.
- TDPyEnvManager setup and the Depth Anything V2 Small model-loading/inference
  lifecycle were successfully tested.

## Input and output

### VERIFIED FROM SOURCE

The extension stores `ownerComp.op('inputImage')` as its input image.  On an
inference request it reads `inputImage.numpyArray(delayed=False,
writable=False)`.  It expects the usual Script-TOP array shape `(height,
width, 4)`, drops alpha, changes BGR to RGB, and scales floating-point samples
by 255 before passing them to the Hugging Face image processor.

After inference, the extension resizes the model prediction to the source
array's original `(height, width)`.  It normalizes that single frame with:

```text
(prediction - prediction.min()) / (prediction.max() - prediction.min())
```

and scales it to 0..65535.  It creates a `(height, width, 4)` `uint16` buffer,
writes the depth value to channel 0 (red), writes zeros to the other channels,
and calls `copyNumpyArray()` on its internal `script1` Script TOP.  Therefore
the named output to consume is the TOP produced by `script1` (or the outer
component connector that exposes it, once verified).

The source contains no explicit image flip, rotation, inversion, or crop in
its TouchDesigner preprocessing/postprocessing path.  Its arrays retain the
input dimensions.

### REQUIRES TOUCHDESIGNER RUNTIME VERIFICATION

- Whether zero-range frames (`max == min`) need guarding in real use.

## Depth meaning and sampling implications

### VERIFIED FROM SOURCE

The output is per-frame min/max normalized relative depth, not metric distance:
the extension deliberately discards the model prediction's absolute scale and
maps each frame to 0..65535.  The source does not invert it or label which end
is near/far.  A helper must call it `depth_raw` (the R/16-bit sample) and/or
`depth_normalized` (0..1), never meters.

The output resolution is the input TOP resolution for each completed frame,
not the model's internal inference resolution. Corresponding YOLO coordinates
can be sampled after converting their normalized coordinates to the depth
TOP's current width/height. Runtime testing confirms that canonical
bottom-left YOLO coordinates align without an additional horizontal or
vertical flip when sampling the synced depth output.

## Parameters and lifecycle

### VERIFIED FROM SOURCE

The extension implements pulse callbacks named `Loadmodel`, `Unloadmodel`,
`Triggerinference`, and `Reset`.  `Loadmodel` asynchronously loads
`depth-anything/Depth-Anything-V2-Small-hf` through the Thread Manager.  The
first load downloads it from Hugging Face to `project.folder/checkpoints/`; a
subsequent load may use that cache.  `Unloadmodel` releases the model/image
processor and clears CUDA cache where available.  `Reset` unloads the model,
replaces output with a small random `uint16` buffer, and marks the component
not ready.

An OP Execute callback calls `parent().DepthInferenceThreaded()` after its
watched operator cooks.  `DepthInferenceThreaded()` only queues work when the
model is ready; it sets `IsReady` false until its success hook copies the
completed output.  This prevents overlapping inferences.  It logs and returns
when the model is absent or inference is already running.

The upstream README also requires a TDPyEnvManager setup using the bundled
`TDPyEnvManagerContext.yaml` and `requirements.txt`, then a TouchDesigner
restart after initial environment creation.  Its initial PyTorch installation
may take several minutes.

### REQUIRES TOUCHDESIGNER RUNTIME VERIFICATION

- The exact custom parameter-page labels and whether inference is automatic
  for the public component's input connection.
- That the Thread Manager and TDPyEnvManager are present and active in the
  target project, and that the installed PyTorch backend selects the intended
  CUDA/MPS/CPU device.
- Model download/cache permissions and first-load completion on the deployment
  machine.

## Minimum manual test

1. Configure TDPyEnvManager, restart TouchDesigner after dependency setup, and
   create/load the model with **Load Model**.
2. Feed a known-orientation color TOP to the component and trigger inference.
3. Confirm that a different source resolution still aligns and that no
   resolution is assumed by downstream helpers.
4. Feed a constant/near-constant image and observe the component's behavior.
