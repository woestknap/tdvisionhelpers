# TDDepthAnything interface reconnaissance

Upstream inspected: `external/TDDepthAnything` at commit
`3e8abb45afda23dde0e90c56dc44caad2820b39b`.

This is an interface record, not a validation of model output.  The source
uses a named internal TOP and Script TOP, while the `.tox` connector layout
must be checked in TouchDesigner.

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

- The external input/output connector indices and whether `inputImage` and
  `script1` are the promoted component connectors.
- The Script TOP's configured pixel format and channel interpretation at the
  public output.  The copied NumPy buffer is `uint16`, but the final TOP
  format must be inspected live.
- TouchDesigner's observed row orientation for `numpyArray()` and the output
  TOP.  Do not assume that the canonical YOLO bottom-left Y maps directly to a
  NumPy row without testing.
- Whether zero-range frames (`max == min`) need guarding in real use.

## Depth meaning and sampling implications

### VERIFIED FROM SOURCE

The output is per-frame min/max normalized relative depth, not metric distance:
the extension deliberately discards the model prediction's absolute scale and
maps each frame to 0..65535.  The source does not invert it or label which end
is near/far.  A helper must call it `depth_raw` (the R/16-bit sample) and/or
`depth_normalized` (0..1), never meters.

The output resolution is the input TOP resolution for each completed frame,
not the model's internal inference resolution.  Corresponding YOLO coordinates
can be sampled after converting their normalized coordinates to the depth
TOP's current width/height.  Because YOLO JSON uses bottom-left normalized Y
and the array row convention is unverified, depth sampling needs an explicit
Y-orientation setting or a one-time calibration check.

### REQUIRES TOUCHDESIGNER RUNTIME VERIFICATION

- Whether larger numerical depth means nearer or farther for this model and
  installed version.  Name any derived inverse value `proximity` only after
  this is confirmed.
- The displayed/output orientation versus the supplied TOP.
- Visual alignment of a same-camera YOLO source and Depth Anything source,
  including any upstream resize/crop/flip outside this extension.

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
3. Confirm the public depth TOP, its resolution, pixel format, and which color
   channel contains depth.
4. Compare a few source pixels to corresponding depth pixels; record whether
   output Y is visually aligned and whether high values denote near or far.
5. Feed a constant/near-constant image and observe the component's behavior.
