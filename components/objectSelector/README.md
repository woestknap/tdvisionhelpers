# objectSelector (Phase 2A)

`objectSelector` selects at most one current object row from the Phase 1 v1
`visionFusion/output` contract. It does not track, smooth, calculate velocity,
sample depth, or alter source fields.

## Custom parameters

Create a custom page named **Object Selector** with these internal parameter
names:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Input DAT | `Inputdat` | OP (DAT) | — |
| Mode | `Mode` | Menu | `highest_confidence` |
| Source Type | `Sourcetype` | String | `object` |
| ID | `Targetid` | Integer | `0` |
| Filter Class | `Filterclass` | Toggle | Off |
| Class ID | `Classid` | Integer | `0` |
| Target X | `Targetx` | Float | `0.5` |
| Target Y | `Targety` | Float | `0.5` |

Use these menu names and labels for `Mode`:

| Menu name | Label |
| --- | --- |
| `id` | ID |
| `highest_confidence` | Highest Confidence |
| `largest` | Largest |
| `nearest` | Nearest |
| `center` | Center |

## Selection behavior

Optional class filtering runs first. When `Filterclass` is enabled, a row is a
candidate only when its numeric/text `class_id` value matches `Classid`.

The selection modes are:

- **ID**: exact `(Sourcetype, Targetid)` identity match.
- **Highest Confidence**: highest valid numeric `confidence`.
- **Largest**: largest valid numeric `width * height`.
- **Nearest**: lowest valid numeric `depth_raw`; empty or invalid depth is not
  eligible.
- **Center**: lowest squared distance from normalized `(center_x, center_y)`
  to `(Targetx, Targety)`.

Ties always retain the first eligible input-table row. There is no tracker
history or sticky target state.

The selected row is copied unchanged. If no row qualifies, `output` contains
only its header. `depth_raw` remains raw relative YOLO depth: lower observed
values are nearer and higher values are farther; it is not metric distance.

## Output schema

```text
source_type, id, class_id, class_name, confidence, center_x, center_y,
width, height, x1, y1, x2, y2, depth_raw, source_frame, source_seq, video_frame
```

## TouchDesigner construction

1. Create a Base COMP named `objectSelector` and add a Table DAT named `output`.
2. Add the custom parameters above and set `Inputdat` to `visionFusion/output`.
3. Add `objectSelectorExt.py` as an extension Text DAT, set its extension
   class to `ObjectSelectorExt`, and promote it. During development, its File
   parameter may point to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/objectSelector/objectSelectorExt.py
   ```

   Use this Extension Object expression:

   ```python
   me.op('objectSelectorExt').module.ObjectSelectorExt(me)
   ```

4. Add an Execute DAT with `objectSelector_execute_callbacks.py` as callbacks;
   enable **Frame End**. Its development File path may be:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/objectSelector/objectSelector_execute_callbacks.py
   ```

5. After changing extension code, pulse **Re-Init Extensions** on the Base COMP.

## Packaging after runtime verification

To distribute a self-contained `objectSelector.tox`, copy the final extension
and Execute DAT code into their internal Text DATs. Disable **Sync to File**,
clear both Text DAT **File** fields, confirm their code remains present, then
save the component as a `.tox`. Reopen that `.tox` from a folder without this
repository and verify it cooks before distribution.
