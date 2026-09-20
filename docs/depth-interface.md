# Historical note: TDDepthAnything evaluation

TDDepthAnything was evaluated during early TDVisionHelpers development and was
later replaced by the public YOLO Depth TOP for Phase 1 depth sampling.

It is no longer a project dependency. This repository does not include setup,
model-loading, environment-management, or runtime instructions for it.

Current Phase 1 depth semantics are documented in
[yolo-interface.md](yolo-interface.md) and
[phase1-design.md](phase1-design.md): sample the public YOLO Depth TOP R
channel as relative, non-metric `depth_raw`; lower observed values are nearer
and higher observed values are farther.
