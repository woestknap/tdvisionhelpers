\# TDVisionHelpers



Free and open-source helper components for computer vision workflows in TouchDesigner.



TDVisionHelpers provides a modular interaction and data-processing layer around existing computer-vision components.



Initial upstream integration:



\- torinmb/yolo-touchdesigner



\## Goals



\- Normalize YOLO detection and tracking data

\- Sample depth data for detected objects

\- Fuse object detection and relative depth

\- Provide TouchDesigner-friendly CHOP/DAT/TOP outputs

\- Add object selection, smoothing, velocity, zones and visualization

\- Keep ML inference separate from helper functionality



\## Architecture



Upstream ML components → adapters → canonical data → helper components



The repositories under `external/` are read-only Git submodules and are not modified by this project.



## Phase 1 quick start

The distributed `.tox` components are the normal end-user installation path:

1. Obtain `yoloData.tox`, `depthSampler.tox`, and `visionFusion.tox`.
2. Add the required `.tox` files to your TouchDesigner project and drop them into the network.
3. Configure their OP parameters:
   - `yoloData`: `Source` → YOLO predictions DAT; optional `Classmap` → class map DAT.
   - `depthSampler`: `Detections` → `yoloData/output`; `Depthtop` → public YOLO Depth TOP.
   - `visionFusion`: `Detections` → `yoloData/output`; `Depth` → `depthSampler/output`.
4. Consume each component's `output` Table DAT. `visionFusion/output` is the fused Phase 1 result.

The packaged `.tox` files contain their required Python DAT code. End users do not need to create Text DATs, extensions, Execute DATs, or reference repository Python files. The `components/` Python files are contributor/development source, not a runtime dependency of the packaged `.tox` files.

Install and configure [yolo-touchdesigner](https://github.com/torinmb/yolo-touchdesigner) separately; it is not bundled with TDVisionHelpers.

See `AGENTS.md` for development guidelines.

