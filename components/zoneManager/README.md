# zoneManager (Phase 3A)

`zoneManager` tests zero, one, or many current canonical object centers against
user-defined rectangular zones and produces compact occupancy plus enter/exit
events. It consumes `smoother/output` directly; velocity is intentionally not
an input because zone membership depends only on center position.

Typical multi-object people-only placement is:

```text
visionFusion
    ↓
classFilter
    ↓
smoother
    ↓
zoneManager
```

## Custom parameters

Create a custom page named **Zone Manager** with these parameters:

| Label | Internal name | Type |
| --- | --- | --- |
| Input DAT | `Inputdat` | OP (DAT) |
| Zones DAT | `Zonesdat` | OP (DAT) |

Set `Inputdat` to `smoother/output`. `Zonesdat` points to a Table DAT with this
exact header:

```text
name
x1
y1
x2
y2
```

Each valid row is an axis-aligned rectangle in normalized coordinates with a
bottom-left origin: X increases right and Y increases up. Boundaries are
inclusive: `x1 <= center_x <= x2` and `y1 <= center_y <= y2`.

Zones may overlap, so an object may occupy multiple zones. Coordinates are not
clamped; rectangles outside `0..1` remain valid. A row with an empty name,
non-finite coordinate, or `x1 > x2` / `y1 > y2` is skipped. Duplicate names
are ambiguous: the first valid occurrence wins and later duplicates are
ignored. Valid zones retain their first-valid-occurrence table order.

## Output contract

`output` contains one row for every current valid identity × valid zone
combination, plus any one-update disappearance exit rows. Normal row ordering
is object-major then zone-minor: input object-row order first, then valid zone
definition order for each object.

```text
zone
inside
entered
exited
source_type
id
```

`inside` is current center-point membership. `entered` pulses for an
outside-to-inside transition; `exited` pulses for an inside-to-outside
transition. Output deliberately does not repeat the full input object row.

The canonical identity is `(source_type, id)`, not `id` alone. Occupancy state
is independent for every `(source_type, id, zone_name)` combination. On a first
valid acquisition, zones containing that object's center emit `entered=1`,
making an object already inside observable. Multiple identities may be inside
the same zone independently.

## Disappearance, reacquisition, and configuration failure

When an identity disappears from an otherwise valid current input, each
still-valid zone it occupied emits one appended exit row using that disappeared
identity. Existing current identities are output first. For several disappeared
identities, exit order follows their previous processed input order where
available, then zone-definition order. The state is removed immediately, so the
next processed sample no longer contains those exit rows. A reappearing identity
is a fresh acquisition and may enter again.

Header-only input is target loss: occupied identities emit their one exit rows,
then later header-only cooks settle to all-zero zone rows with blank identity,
preserving the original single-object behavior. Missing `Inputdat` or malformed
object schema is a configuration/input failure: it clears all object state and
outputs all-zero zone rows without synthetic exits. Invalid individual rows are
skipped; an identity represented only by invalid data is treated as absent and
may produce normal disappearance exits. Missing or malformed `Zonesdat` resets
all state and outputs only the header.

## Runtime zone edits and event pulses

Zone definitions are parsed every logical update. History is retained by valid
zone name for every identity while that name continues to exist. Coordinate
changes therefore produce normal per-identity enter/exit transitions; a newly
added zone starts outside for every identity and can enter immediately. Removed
zones disappear without synthetic exits. A malformed row that later becomes
valid is treated as newly added.

The component deduplicates the complete ordered set of valid object rows plus
parsed zone definitions. A change for one object still processes all current
objects, while each object's own occupancy remains independent. Repeated
identical cooks never replay transitions. After a transition is written, the
next identical cook clears `entered` and `exited` to zero while retaining
occupancy, so event flags do not stick high.

## TouchDesigner construction

1. Create a Base COMP named `zoneManager` and add a Table DAT named `output`.
2. Optionally create a local Table DAT such as `zones` for development, using
   the `name, x1, y1, x2, y2` header above.
3. Add the **Zone Manager** custom page and its `Inputdat` and `Zonesdat` OP
   parameters. Point them to `smoother/output` and the zones Table DAT. Both
   the original one-row `objectSelector → smoother → zoneManager` workflow and
   multi-row canonical input are supported.
4. Add an extension Text DAT named `zoneManagerExt`, set its extension class to
   `ZoneManagerExt`, and promote it. During development, set its File parameter
   to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/zoneManager/zoneManagerExt.py
   ```

   Use this Extension Object expression:

   ```python
   me.op('zoneManagerExt').module.ZoneManagerExt(me)
   ```

5. Add an Execute DAT with `zoneManager_execute_callbacks.py` as callbacks and
   enable **Frame End**. Its development File parameter may point to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/zoneManager/zoneManager_execute_callbacks.py
   ```

6. After changing extension code, pulse **Re-Init Extensions** on the Base
   COMP.

## Packaging after runtime verification

To distribute a self-contained `zoneManager.tox`, copy the final extension and
Execute DAT code into their internal Text DATs. Disable **Sync to File**, clear
both Text DAT **File** fields, pulse **Re-Init Extensions**, confirm embedded
code remains present, then save the component as `zoneManager.tox`. Reopen it
from a folder without this repository and confirm it cooks before distribution.
