# graphicSelector

`graphicSelector` assigns one stable graphic slot to each current canonical
identity. It prepares assignment data only; a future multi-source
`graphicAttachment` can resolve each assigned slot to an actual TOP or effect.

The assignment identity is `(source_type, id)`. The anchor and all transform
values are deliberately excluded, so a person keeps the same assignment while
its attachment point, movement, confidence, or source-frame metadata changes.

## Source registry

Add a root Table DAT named `sources` with this exact schema:

```text
name,enabled,weight
```

For example:

```text
name,enabled,weight
halo,1,1
glitch,1,1
flames,1,1
```

`name` must be non-empty; `enabled` is interpreted logically; `weight` must be
finite and non-negative. Duplicate names are allowed and are separate slots.

Slots use the physical zero-based source data-row position: registry row 1 is
slot `0`, row 2 is `1`, and so on. Disabled/invalid rows retain their physical
position but cannot be selected. Weight-zero rows are selectable in fixed and
round-robin modes but not random mode.

## Parameters

Create a **Graphic Selector** page with:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Input DAT | `Inputdat` | OP | `transformStabilizer/stabilizedTransformData` |
| Sources DAT | `Sourcesdat` | OP | internal `sources` DAT |
| Mode | `Mode` | Menu: `fixed`, `round_robin`, `random` | `random` |
| Fixed Index | `Fixedindex` | Integer | `0` |
| Seed | `Seed` | Integer | `1` |
| Reassign | `Reassign` | Pulse | — |
| Enabled | `Enabled` | Toggle | On |

Add a Parameter Execute DAT for the `Reassign` pulse whose `onPulse` callback
calls:

```python
parent().Reassign()
```

The next Frame End rebuilds assignments for current identities.

## Output

Add a root Table DAT named `assignmentData` with this exact header:

```text
source_type,id,graphic_index,graphic_name,visible,source_frame,source_seq,video_frame
```

It emits one row per valid input identity row in input order. Duplicate input
rows with the same `(source_type, id)` remain duplicate output rows and share
the assignment. Input `visible=0` retains the assignment but outputs
`visible=0`; returning to visible later reuses it.

## Modes and persistence

- **fixed:** assigns only `Fixedindex`. If that physical slot is invalid or
  disabled, the row keeps blank graphic fields and becomes invisible.
- **round_robin:** new identities cycle through selectable physical slots.
  Existing assignments are not renumbered when another identity disappears.
- **random:** new identities receive a weighted choice among enabled,
  positive-weight slots. A component-local `random.Random(Seed)` generator
  provides deterministic assignment order without touching global random state.

Assignments persist while an identity remains present. They are removed at
disappearance. Mode, seed, fixed-index, and Reassign changes reset all current
assignments. Position/frame changes do not consume random numbers.

Registry edits preserve an assignment when its physical slot remains selectable
for the active mode. If a slot is removed or disabled, only identities assigned
to that slot are reassigned. Random weight changes affect future selections but
do not reshuffle existing valid assignments.

With `Enabled` off, every accepted input row is retained with blank graphic
fields and `visible=0`; assignment state is cleared, so enabling begins fresh.
Missing/header-only/malformed input produces a header-only output and clears
state.

## Manual TouchDesigner setup

1. Create Base COMP `graphicSelector` with root Table DATs `sources` and
   `assignmentData`.
2. Add the **Graphic Selector** parameters above and point `Sourcesdat` to the
   internal `sources` DAT.
3. Add Text DAT `graphicSelectorExt` from `graphicSelectorExt.py`, set its
   extension class to `GraphicSelectorExt`, promote it, and use:

   ```python
   me.op('graphicSelectorExt').module.GraphicSelectorExt(me)
   ```

4. Add an Execute DAT using `graphicSelector_execute_callbacks.py`; enable
   **Frame End**.
5. Add a Parameter Execute DAT for `Reassign` as documented above.
6. Point `Inputdat` at `transformStabilizer/stabilizedTransformData`. Test all
   modes, disabled slots, duplicate names/identities, disappearance, temporary
   invisibility, seed changes, registry changes, and the pulse.

## Deliberate exclusions

The component does not resolve TOP paths, render, choose per-person TOPs,
animate, track, smooth, associate objects with poses, sample depth, process
face landmarks, apply FM effects, or preserve assignments across disappeared
tracker IDs.
