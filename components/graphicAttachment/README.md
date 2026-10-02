# graphicAttachment

`graphicAttachment` resolves current attachment transforms to graphic TOP
sources and prepares data for a native replicated TouchDesigner rendering
network. It does not render pixels, track identities, select graphics, or
associate poses to objects. Canonical identity is `(source_type, id)`.

It accepts zero, one, or many transform rows in input order. Multiple anchor
rows for the same identity share that identity's assigned graphic source.

## Public parameters

Create these parameters on the existing custom parameter page:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Image TOP | `Imagetop` | OP | — |
| Graphic TOP | `Graphictop` | OP | — |
| Transform DAT | `Transformdat` | OP | `transformStabilizer/transformData` |
| Assignments DAT | `Assignmentsdat` | OP | `graphicSelector/assignmentData` |
| Sources DAT | `Sourcesdat` | OP | `graphicsSources` |
| Multi Source | `Multisource` | Toggle | On |
| Scale Multiplier | `Scalemultiplier` | Float | `1.0` |
| Rotation Offset | `Rotationoffset` | Float, degrees | `0.0` |
| X Offset | `Xoffset` | Float, normalized | `0.0` |
| Y Offset | `Yoffset` | Float, normalized | `0.0` |
| Opacity | `Opacity` | Float | `1.0` |
| Show Graphic | `Showgraphic` | Toggle | On |

`Opacity` is clamped to `0..1`. `Showgraphic` handles normal TouchDesigner
Toggle booleans: Off makes every prepared row non-visible.

With `Multisource` On, `Assignmentsdat` and `Sourcesdat` resolve each graphic.
With it Off, previous one-`Graphictop` behaviour is preserved: native rendering
uses `Graphictop` and its absence does not make rows non-visible. In this mode
`graphic_index` and `graphic_name` are blank; `graphic_top` is optionally the
configured TOP path.

## Input contracts

`Transformdat` expects:

```text
source_type,id,anchor,x,y,scale,rotation,confidence,visible,source_frame,source_seq,video_frame
```

`Assignmentsdat` expects:

```text
source_type,id,graphic_index,graphic_name,visible,source_frame,source_seq,video_frame
```

Create a root Table DAT `graphicsSources` with exactly:

```text
name,top
```

Each physical data-row position is its graphic slot: the first data row is
`graphic_index=0`, the second is `1`, and so on. Keep blank/disabled slots in
place; the controller never compacts or renumbers this table. A valid registry
name overrides the assignment's `graphic_name`. An empty `top`, missing slot,
or invalid assignment makes the transform non-visible. Duplicate assignment
identities use the first valid assignment row.

## Prepared tables

Create these root Table DATs.

### `graphicTransformData`

It always has this exact schema:

```text
source_type,id,anchor,x,y,scale,rotation,opacity,visible,graphic_index,graphic_name,graphic_top,source_frame,source_seq,video_frame
```

Coordinates remain normalized: origin bottom-left, X right, Y up.

```text
x        = input_x + Xoffset
y        = input_y + Yoffset
scale    = input_scale * Scalemultiplier
rotation = input_rotation + Rotationoffset
opacity  = clamp(Opacity, 0, 1)
```

In multi-source mode, the assignment joins strictly by `(source_type, id)`.
Its physical `graphic_index` selects `graphicsSources`; the registry provides
the output `graphic_name` and `graphic_top`. Assignment visibility, a non-empty
resolved TOP, valid transform numbers, source visibility, and `Showgraphic`
must all be true for `visible=1`. A missing or malformed join preserves the
transform row but blanks the graphic fields and sets `visible=0`.

Missing, header-only, or malformed transform input produces a header-only
prepared table. A malformed transform row does not affect its siblings.

### `graphicReplicas`

This root Table DAT has exactly one column:

```text
name
```

It contains `item1` through `itemN` for the number of currently visible
prepared rows. It is rewritten only when that visible count changes, avoiding
Replicator rebuilds for ordinary transform updates.

### `graphicReplicaMap`

This root Table DAT has exactly:

```text
replica_index,transform_row
```

It is refreshed every frame. `replica_index` is the zero-based visible-replica
position; `transform_row` is the zero-based data-row position in
`graphicTransformData` (excluding its header). This maps a sequential replica
to the correct potentially non-contiguous visible transform row.

## Native TouchDesigner rendering setup

1. Add root Tables `graphicsSources`, `graphicTransformData`,
   `graphicReplicas`, and `graphicReplicaMap` with the exact schemas above.
2. Configure stable physical source slots in `graphicsSources`; point
   `Assignmentsdat` to `graphicSelector/assignmentData`, `Sourcesdat` to the
   registry, and `Transformdat` to `transformStabilizer/transformData`.
3. Use `graphicReplicas` as a Replicator COMP Template DAT. Its replicas are
   `item1`, `item2`, and so on.
4. In the replica callback, use `graphicReplicaMap` to map its zero-based item
   number to the required `graphicTransformData` data row. Feed that row's
   `graphic_top`, x/y/scale/rotation/opacity into the native transform and
   composite network.
5. Keep the existing `Graphictop` path for `Multisource` Off. Do not use the
   live transform table as the Replicator template.
6. Render in normalized bottom-left image coordinates, use `Imagetop` for
   output resolution, and Composite graphics Over the image.

## Extension setup and checks

Add a Text DAT from `graphicAttachmentExt.py`, set its extension class to
`GraphicAttachmentExt`, and use:

```python
me.op('graphicAttachmentExt').module.GraphicAttachmentExt(me)
```

Add an Execute DAT using `graphicAttachment_execute_callbacks.py` and enable
**Frame End**.

Manually test distinct slots for two identities, several anchors for one
identity, hidden assignments, blank source TOPs, missing/invalid indices,
duplicate assignment identities, and blank intermediate registry rows. Verify
that physical slot indices do not shift, only visible-count changes rebuild
replicas, and the map follows non-contiguous visible transform rows.
