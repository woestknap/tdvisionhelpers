# zoneManager (Phase 3A)

`zoneManager` tests the current selected/smoothed object's center point against
user-defined rectangular zones and produces compact occupancy plus enter/exit
events. It consumes `smoother/output` directly; velocity is intentionally not
an input because zone membership depends only on center position.

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

`output` contains one row for each current valid unique zone:

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

The canonical identity is `(source_type, id)`, not `id` alone. On a first valid
acquisition, zones containing the center emit `entered=1`, making an object
already inside observable.

## Identity, target loss, and configuration failure

On an identity change, the first new-object sample emits exits for zones the
previous object occupied, with that previous identity on exit rows. The new
identity becomes pending and does not emit its enters in that same update. Its
next genuinely processed sample evaluates membership and emits its enters.

On header-only target loss, occupied zones emit one exit pulse using the prior
identity. Later header-only cooks settle to all-zero rows with blank identity.
When an object reappears, it is a fresh acquisition.

Missing `Inputdat`, malformed object schema, or invalid/non-finite center is a
configuration/input failure rather than target loss. It resets state and
outputs zero rows with blank identity, without synthetic exits. Missing or
malformed `Zonesdat` resets all state and outputs only the header.

## Runtime zone edits and event pulses

Zone definitions are parsed every logical update. History is preserved by zone
name while that name remains valid. Changing coordinates can therefore create
normal enter/exit events; a new zone starts outside and can enter immediately.
Removed zones disappear without synthetic exit rows. A malformed row that later
becomes valid is treated as newly added.

The component deduplicates the logical pair of full object-row content and
parsed zone definitions. Repeated identical cooks never replay a transition.
After a transition is written, the next identical cook clears `entered` and
`exited` to zero while retaining occupancy, so event flags do not stick high.

## TouchDesigner construction

1. Create a Base COMP named `zoneManager` and add a Table DAT named `output`.
2. Optionally create a local Table DAT such as `zones` for development, using
   the `name, x1, y1, x2, y2` header above.
3. Add the **Zone Manager** custom page and its `Inputdat` and `Zonesdat` OP
   parameters. Point them to `smoother/output` and the zones Table DAT.
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
