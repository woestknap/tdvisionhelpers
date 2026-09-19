"""TouchDesigner extension for the Phase 1B depthSampler component.

Attach this extension to a Base COMP containing a Table DAT named ``output``.
``Detections`` points to yoloData/output and ``Depthtop`` points to the
spatially aligned TDDepthAnything depth TOP.
"""

import math

import numpy as np


class DepthSamplerExt:
    """Sample relative depth from an inner ROI for each current object row."""

    HEADER = (
        'source_type',
        'id',
        'depth_value',
        'source_frame',
        'source_seq',
        'video_frame',
    )
    INNER_ROI_SCALE = 0.5
    REQUIRED_COLUMNS = (
        'source_type',
        'id',
        'x1',
        'y1',
        'x2',
        'y2',
        'source_frame',
        'source_seq',
        'video_frame',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')

    def Update(self):
        """Write one relative-depth row per valid current object detection."""
        if self.output is None:
            return

        detections = self._configured_op('Detections')
        detection_rows = self._read_detection_rows(detections)
        if not detection_rows:
            self._write_rows(())
            return

        depth_top = self._configured_op('Depthtop')
        depth_channel = self._read_depth_channel(depth_top)
        if depth_channel is None:
            self._write_rows(())
            return

        rows = []
        for detection in detection_rows:
            depth_value = self._sample_inner_roi(depth_channel, detection)
            if depth_value is None:
                continue
            rows.append((
                detection['source_type'],
                detection['id'],
                depth_value,
                detection['source_frame'],
                detection['source_seq'],
                detection['video_frame'],
            ))
        self._write_rows(rows)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _read_detection_rows(self, detections):
        if detections is None:
            return ()
        try:
            headers = [cell.val for cell in detections.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.REQUIRED_COLUMNS
            }
        except Exception:
            return ()

        rows = []
        try:
            num_rows = detections.numRows
        except Exception:
            return ()
        for row_index in range(1, num_rows):
            try:
                values = {
                    column: detections[row_index, index].val
                    for column, index in column_indices.items()
                }
            except Exception:
                continue
            if values['source_type'] != 'object' or values['id'] in (None, ''):
                continue
            box = self._normalized_box(values)
            if box is None:
                continue
            values.update(box)
            rows.append(values)
        return rows

    @staticmethod
    def _normalized_box(values):
        try:
            x1 = float(values['x1'])
            y1 = float(values['y1'])
            x2 = float(values['x2'])
            y2 = float(values['y2'])
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            return None
        if not (0.0 <= x1 <= x2 <= 1.0 and 0.0 <= y1 <= y2 <= 1.0):
            return None
        return {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

    @staticmethod
    def _read_depth_channel(depth_top):
        if depth_top is None:
            return None
        try:
            depth_array = depth_top.numpyArray(delayed=False, writable=False)
        except Exception:
            return None
        if depth_array is None or depth_array.ndim < 2:
            return None
        if depth_array.ndim == 2:
            return depth_array
        if depth_array.shape[2] < 1:
            return None
        return depth_array[:, :, 0]

    def _sample_inner_roi(self, depth_channel, detection):
        height, width = depth_channel.shape[:2]
        if width < 1 or height < 1:
            return None

        x1, y1, x2, y2 = self._inner_box(detection)
        left = max(0, min(width, int(math.floor(x1 * width))))
        right = max(0, min(width, int(math.ceil(x2 * width))))

        # NumPy rows begin at the image top; canonical Y begins at the bottom.
        top = max(0, min(height, int(math.floor((1.0 - y2) * height))))
        bottom = max(0, min(height, int(math.ceil((1.0 - y1) * height))))
        if right <= left or bottom <= top:
            return None

        roi = depth_channel[top:bottom, left:right]
        valid = roi[np.isfinite(roi)]
        if valid.size == 0:
            return None

        depth_value = float(np.median(valid))
        if not math.isfinite(depth_value):
            return None
        return self._normalize_depth_value(depth_value, depth_channel.dtype)

    def _inner_box(self, detection):
        x1, y1, x2, y2 = (
            detection['x1'],
            detection['y1'],
            detection['x2'],
            detection['y2'],
        )
        center_x = (x1 + x2) * 0.5
        center_y = (y1 + y2) * 0.5
        half_width = (x2 - x1) * self.INNER_ROI_SCALE * 0.5
        half_height = (y2 - y1) * self.INNER_ROI_SCALE * 0.5
        return (
            center_x - half_width,
            center_y - half_height,
            center_x + half_width,
            center_y + half_height,
        )

    @staticmethod
    def _normalize_depth_value(value, dtype):
        if np.issubdtype(dtype, np.integer):
            value /= float(np.iinfo(dtype).max)
        return max(0.0, min(1.0, value))

    def _write_rows(self, rows):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        for row in rows:
            self.output.appendRow(row)
