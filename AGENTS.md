\## External directory



The entire `external/` directory is READ-ONLY reference material.



Never modify, format, refactor, commit changes to, or generate files inside:



\- external/yolo-touchdesigner/



This is a Git submodule tracking an upstream project.



All TDVisionHelpers code must live outside `external/`.



If an upstream change appears necessary, report the requirement instead of modifying the upstream repository.



\# TDVisionHelpers — Codex Instructions



\## Project purpose



TDVisionHelpers is a free/open TouchDesigner helper toolkit that consumes

computer-vision data from existing TouchDesigner components.



Initial supported upstream component:



1\. torinmb/yolo-touchdesigner

&#x20;  https://github.com/torinmb/yolo-touchdesigner



The project provides adapters, data normalization, visualization,

tracking utilities, depth sampling, fusion, interaction helpers,

zones and debugging tools.



It does NOT implement or replace ML inference.



\---



\## Core architectural rule



UPSTREAM ML COMPONENTS -> ADAPTERS -> CANONICAL DATA -> HELPERS



Never make downstream helper components depend directly on undocumented

internal operators of an upstream component when an adapter can isolate

that dependency.



Only adapter components should understand upstream-specific schemas.



\---



\## Upstream repositories



Treat both upstream repositories as external dependencies.



Do not modify their source unless explicitly instructed.



Do not:



\- rewrite YOLO inference

\- move ML inference into TDVisionHelpers

\- modify upstream WebSocket/server code

\- modify upstream model files

\- duplicate upstream functionality without a clear reason



Prefer consuming documented/exposed outputs.



\---



\## Canonical coordinates



Use normalized coordinates whenever possible.



X = 0.0 to 1.0

Y = 0.0 to 1.0



Document coordinate origin and orientation.



Do not silently mix pixel and normalized coordinates.



\---



\## Canonical detection data



Normalized detection records should support:



id

class\_id

class\_name

confidence

center\_x

center\_y

width

height

x1

y1

x2

y2



Optional enriched fields:



depth\_raw

depth\_normalized

velocity\_x

velocity\_y

velocity\_depth

age

visible



Missing data must have a predictable representation.



\---



\## Depth semantics



Relative depth output must be treated as non-metric unless the

specific upstream model/configuration explicitly provides metric depth.



Never label relative depth as meters.



Use names such as:



depth\_raw

depth\_normalized

proximity



Metric distance support may be implemented later as a separate

calibration layer.



\---



\## TouchDesigner design principles



Components should behave like native TouchDesigner tools.



Prefer:



\- clear custom parameter pages

\- meaningful parameter names

\- pulse parameters for actions

\- CHOP output for continuous numeric control data

\- DAT output for structured object data

\- TOP output for visualization

\- normalized values

\- sensible defaults



Avoid unnecessary dependencies.



Components should fail gracefully when inputs are missing.



Do not generate excessive console output during normal operation.



Debug logging should be optional.



\---



\## Performance



This project is intended for real-time use.



Avoid:



\- unnecessary per-frame Python allocations

\- repeated operator searches

\- unnecessary TOP -> NumPy -> TOP transfers

\- blocking operations in frame callbacks

\- rebuilding static structures every frame



Cache operator references where safe.



Prefer TouchDesigner-native operations where they are significantly

more efficient than Python.



Optimize only after correctness unless an implementation is obviously

unsuitable for real-time operation.



\---



\## Depth sampling



Do not assume the center pixel of a YOLO bounding box represents

object depth.



Depth sampling should support robust ROI methods.



Preferred initial default:



median depth from a reduced inner bounding-box region.



Architecture should allow future sampling strategies including:



center

median ROI

inner ROI

lower center

pose torso

custom point



\---



\## Tracking



Persistent YOLO IDs should remain intact whenever provided upstream.



TDVisionHelpers should not create a competing tracker unless explicitly

required.



Smoothing and velocity estimation must be separate from identity

tracking.



\---



\## Modularity



Each helper should perform one primary responsibility.



Examples:



yoloData

depthSampler

visionFusion

objectSelector

smoother

velocity

zoneManager

debugVisualizer



Avoid creating one monolithic component.



\---



\## Compatibility



Do not hard-code assumptions about a user's camera resolution.



Do not hard-code absolute project operator paths where relative

references can be used.



External component locations should be configurable when appropriate.



\---



\## Code quality



Prefer straightforward readable Python over clever abstractions.



Use:



\- descriptive names

\- small functions

\- docstrings where useful

\- comments explaining TouchDesigner-specific behavior



Avoid:



\- unnecessary frameworks

\- speculative abstractions

\- premature generalized plugin systems

\- large dependency additions



\---



\## Documentation



Whenever an upstream interface is discovered, document it in:



docs/yolo-interface.md



or



docs/depth-interface.md



Record:



\- operator/output name

\- schema

\- coordinate system

\- data type

\- observed assumptions

\- upstream version/commit if available



This prevents future agents from repeatedly rediscovering the interface.



\---



\## Working method



Before implementing a component:



1\. inspect relevant existing code

2\. identify the exact upstream interface

3\. document it

4\. propose the smallest implementation

5\. implement it

6\. validate syntax/static behavior

7\. report what still requires testing inside TouchDesigner



Do not redesign unrelated parts of the repository.



\---



\## Token/compute efficiency



Keep repository exploration targeted.



Do not repeatedly inspect files that have already been documented.



Read architecture and interface documentation before exploring upstream

repositories.



Do not perform broad refactors without explicit reason.



Prefer small complete tasks over large speculative changes.



When uncertain about a TouchDesigner runtime behavior that cannot be

verified outside TouchDesigner, document the uncertainty rather than

repeatedly attempting speculative fixes.



\---



\## Testing limitations



Codex may not have a running TouchDesigner environment.



Never claim that TouchDesigner runtime behavior has been verified unless

it actually has.



Separate validation into:



STATIC VERIFIED

RUNTIME REQUIRES TOUCHDESIGNER



Provide concise manual test instructions for runtime-only behavior.



\---



\## Scope control



Do not add features merely because they seem useful.



Implement only the requested task plus changes genuinely required to

support it.



If a major architectural change appears necessary, explain why before

performing it.

## Canonical identity

YOLO object tracking and pose tracking use independent tracker namespaces.

Never assume that object ID 1 and pose ID 1 represent the same entity.

Canonical records must identify their source/stream in addition to preserving
the upstream ID.

A globally meaningful key is therefore `(source_type, id)`, not `id` alone.

Do not attempt to associate object detections with pose detections unless an
explicit association component is implemented later.


## Canonical coordinate system

TDVisionHelpers canonical image coordinates are normalized 0.0..1.0.

Origin: bottom-left.

X increases left-to-right.
Y increases bottom-to-top.

Adapters are responsible for converting upstream coordinates into this
convention.

Consumers must not depend on an upstream coordinate convention directly.


## Frame metadata

Preserve available upstream frame metadata.

YOLO canonical detection records should retain:

source_frame
source_seq
video_frame

Do not discard synchronization metadata that may be useful for latency,
staleness, or future frame association.


## Phase 1 depth

Phase 1 depth sampling consumes the public YOLO Depth TOP through an explicit
component parameter. Preserve its sampled value as `depth_raw`.

`depth_raw` is a relative, non-metric value. Lower observed values are nearer
and higher observed values are farther. Do not normalize, clamp, invert, or
convert it to physical units. Do not create a synthetic proximity value.

Do not derive metric distance or depth velocity from these values. Do not
implement `velocity_depth` until a temporally stable depth representation is
available.


## Phase 1 scope

Phase 1 yoloData supports standard YOLO object detections only.

Pose/keypoint adaptation is deferred to a dedicated poseData component.

Do not add pose support to yoloData during Phase 1.
