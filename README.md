\# TDVisionHelpers



Free and open-source helper components for computer vision workflows in TouchDesigner.



TDVisionHelpers provides a modular interaction and data-processing layer around existing computer-vision components.



Initial upstream integrations:



\- torinmb/yolo-touchdesigner

\- TouchDesigner/TDDepthAnything



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



See `AGENTS.md` for development guidelines.

