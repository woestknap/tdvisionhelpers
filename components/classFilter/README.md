# classFilter

`classFilter` is a stateless, multi-row canonical-DAT filter. Unlike
`objectSelector`, it does not select or reduce objects: it keeps every valid
row whose integer `class_id` satisfies the configured include/exclude rule.

Typical placement is:

```text
visionFusion
    ↓
classFilter
    ↓
smoother
```

## Custom parameters

Create a custom page named **Class Filter** with these parameters:

| Label | Internal name | Type | Default |
| --- | --- | --- | --- |
| Input DAT | `Inputdat` | OP (DAT) | — |
| Mode | `Mode` | Menu | `include` |
| Classes | `Classes` | String | `0` |

Use these menu names and labels for `Mode`:

| Menu name | Label |
| --- | --- |
| `include` | Include |
| `exclude` | Exclude |

`Classes` is a comma-separated list of integer class IDs. Whitespace is
allowed; duplicates are harmless; invalid entries are ignored; and negative IDs
are supported. Examples: `0`, `0,16`, and `0, 16, 17`.

## Behavior

Input is a canonical multi-object DAT such as `visionFusion/output`:

```text
source_type
id
class_id
class_name
confidence
center_x
center_y
width
height
x1
y1
x2
y2
depth_raw
source_frame
source_seq
video_frame
```

The output has the exact same header and contains matching full input rows in
their original order. Rows are copied unchanged: coordinates, identity, class
information, confidence, raw depth, and source metadata are never reformatted
or altered.

- **Include**: retain rows whose integer `class_id` appears in `Classes`.
- **Exclude**: retain rows whose integer `class_id` does not appear in `Classes`.

For the currently tested YOLO adapter, people use `class_id = 0`, so
`Mode = include` and `Classes = 0` retains every current person row. This is an
example only; `classFilter` has no person-specific behavior.

A missing, blank, or non-integer row `class_id` is not eligible for either mode
and is skipped. With no valid IDs in `Classes`, Include produces header-only
output and Exclude passes all valid-class rows. Missing input, a header-only
input, or a malformed canonical schema produces header-only output gracefully.

## TouchDesigner construction

1. Create a Base COMP named `classFilter` and add a Table DAT named `output`.
2. Add the **Class Filter** custom page and parameters above. Set `Inputdat` to
   `visionFusion/output` or another canonical DAT with the same schema.
3. Add an extension Text DAT named `classFilterExt`, set its extension class to
   `ClassFilterExt`, and promote it. During development, set its File parameter
   to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/classFilter/classFilterExt.py
   ```

   Use this Extension Object expression:

   ```python
   me.op('classFilterExt').module.ClassFilterExt(me)
   ```

4. Add an Execute DAT with `classFilter_execute_callbacks.py` as callbacks and
   enable **Frame End**. Its development File parameter may point to:

   ```text
   C:/Users/ruudd/tdvisionhelpers/components/classFilter/classFilter_execute_callbacks.py
   ```

5. After changing extension code, pulse **Re-Init Extensions** on the Base
   COMP.

## Packaging after runtime verification

To distribute a self-contained `classFilter.tox`, copy the final extension and
Execute DAT code into their internal Text DATs. Disable **Sync to File**, clear
both Text DAT **File** fields, confirm embedded code remains present, then save
the component as `classFilter.tox`. Reopen it from a folder without this
repository and verify it cooks before distribution.
