# yoloData (Phase 1A)

`yoloData` adapts current standard-object detections from the locally
configured yolo-touchdesigner `predictions` DAT to one canonical Table DAT.
It supports only upstream `type: "yolo"` and the `yolo` array of
`type: "yolo_combined"`.  It deliberately ignores `yolo_pose`.

## Build the component in TouchDesigner

1. Create a Base COMP named `yoloData` and add a Table DAT named `output`.
2. Add custom OP parameters to the Base COMP:
   - `Source` (label: **Source DAT**) — required; point it at the
     yolo-touchdesigner `predictions` DAT.
   - `Classmap` (label: **Class Map DAT**) — optional; point it at a Table DAT
     with `class_id` and `class_name` header cells.
3. Add `yoloDataExt.py` as an extension DAT (the development Text DAT may
   reference the external file), set its extension class to `YoloDataExt`, and
   promote the extension. Set its **Extension Object** expression to:

   ```python
   me.op('yoloDataExt').module.YoloDataExt(me)
   ```
4. Add an Execute DAT with `yoloData_execute_callbacks.py` as its callbacks.
   Enable **Frame End**.  This calls `parent().Update()` after the upstream
   source has had a chance to cook.

The `output` DAT is the component output.  It has one header row and one row
per current valid object detection.  It is header-only for zero detections,
missing input, invalid JSON, unsupported message types, and malformed records.
No errors are printed for those expected runtime states.

## Output schema

```text
source_type, id, class_id, class_name, confidence, center_x, center_y,
width, height, x1, y1, x2, y2, source_frame, source_seq, video_frame
```

All geometry is normalized with bottom-left origin, X increasing right, and Y
increasing up.  `source_type` is always `object`.  `id` and frame metadata are
copied directly from the upstream message.  `class_name` remains empty without
a valid Class Map DAT.

The extension compares the source DAT text each frame, so unchanged JSON is
not reparsed and the output table is not rebuilt.  It does not rely on the
source DAT cook count because the live upstream DAT can change text without a
reliably changing count.  Class Map DAT data remains cook-count cached.  The
component does not track, smooth, retain historical records, or adapt pose
data.
