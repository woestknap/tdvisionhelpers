"""TouchDesigner extension for the Phase 1C visionFusion component."""

import math


class VisionFusionExt:
    """Join current canonical object detections with frame-compatible depth."""

    DETECTION_COLUMNS = (
        'source_type',
        'id',
        'class_id',
        'class_name',
        'confidence',
        'center_x',
        'center_y',
        'width',
        'height',
        'x1',
        'y1',
        'x2',
        'y2',
        'source_frame',
        'source_seq',
        'video_frame',
    )
    DEPTH_COLUMNS = (
        'source_type',
        'id',
        'depth_raw',
        'source_frame',
        'source_seq',
        'video_frame',
    )
    HEADER = (
        'source_type',
        'id',
        'class_id',
        'class_name',
        'confidence',
        'center_x',
        'center_y',
        'width',
        'height',
        'x1',
        'y1',
        'x2',
        'y2',
        'depth_raw',
        'source_frame',
        'source_seq',
        'video_frame',
    )
    FRAME_COLUMNS = ('source_frame', 'source_seq', 'video_frame')
    NUMERIC_DETECTION_COLUMNS = (
        'confidence',
        'center_x',
        'center_y',
        'width',
        'height',
        'x1',
        'y1',
        'x2',
        'y2',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')
        self._detections_dat = None
        self._detections_text = None
        self._depth_dat = None
        self._depth_text = None
        self._has_written_output = False

    def Update(self, force=False):
        """Write fused current-frame object rows when either input DAT changes."""
        if self.output is None:
            return

        detections_dat = self._configured_op('Detections')
        depth_dat = self._configured_op('Depth')
        detections_text = self._dat_text(detections_dat)
        depth_text = self._dat_text(depth_dat)
        inputs_changed = (
            detections_dat is not self._detections_dat
            or detections_text != self._detections_text
            or depth_dat is not self._depth_dat
            or depth_text != self._depth_text
        )
        if not force and self._has_written_output and not inputs_changed:
            return

        self._detections_dat = detections_dat
        self._detections_text = detections_text
        self._depth_dat = depth_dat
        self._depth_text = depth_text

        detection_rows = self._read_rows(detections_dat, self.DETECTION_COLUMNS)
        depth_rows = self._read_rows(depth_dat, self.DEPTH_COLUMNS)
        depth_by_key = self._depth_by_key(depth_rows)
        self._write_rows(self._fused_rows(detection_rows, depth_by_key))
        self._has_written_output = True

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    @staticmethod
    def _dat_text(dat):
        if dat is None:
            return ''
        try:
            return dat.text
        except Exception:
            return ''

    @staticmethod
    def _read_rows(dat, required_columns):
        if dat is None:
            return ()
        try:
            headers = [cell.val for cell in dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in required_columns
            }
            num_rows = dat.numRows
        except Exception:
            return ()

        rows = []
        for row_index in range(1, num_rows):
            try:
                rows.append({
                    column: dat[row_index, index].val
                    for column, index in column_indices.items()
                })
            except Exception:
                continue
        return rows

    def _depth_by_key(self, depth_rows):
        """Return unambiguous, frame-compatible raw-depth values by identity."""
        depth_by_key = {}
        for row in depth_rows:
            key = self._frame_key(row)
            if key is None or not self._valid_depth_raw(row.get('depth_raw')):
                continue
            if key in depth_by_key:
                # A duplicate exact key is ambiguous: leave depth missing.
                depth_by_key[key] = None
            else:
                depth_by_key[key] = row['depth_raw']
        return depth_by_key

    def _fused_rows(self, detection_rows, depth_by_key):
        rows = []
        for detection in detection_rows:
            if not self._valid_detection(detection):
                continue
            depth_raw = depth_by_key.get(self._frame_key(detection), '')
            if depth_raw is None:
                depth_raw = ''
            rows.append((
                detection['source_type'],
                detection['id'],
                detection['class_id'],
                detection['class_name'],
                detection['confidence'],
                detection['center_x'],
                detection['center_y'],
                detection['width'],
                detection['height'],
                detection['x1'],
                detection['y1'],
                detection['x2'],
                detection['y2'],
                depth_raw,
                detection['source_frame'],
                detection['source_seq'],
                detection['video_frame'],
            ))
        return rows

    def _valid_detection(self, row):
        if row.get('source_type') != 'object' or row.get('id') in (None, ''):
            return False
        if row.get('class_id') in (None, ''):
            return False
        return all(
            self._valid_number(row.get(column))
            for column in self.NUMERIC_DETECTION_COLUMNS
        )

    def _frame_key(self, row):
        source_type = row.get('source_type')
        source_id = row.get('id')
        frame_values = tuple(row.get(column) for column in self.FRAME_COLUMNS)
        if source_type in (None, '') or source_id in (None, ''):
            return None
        if any(value in (None, '') for value in frame_values):
            return None
        return (source_type, source_id) + frame_values

    @staticmethod
    def _valid_depth_raw(value):
        return VisionFusionExt._valid_number(value)

    @staticmethod
    def _valid_number(value):
        if value in (None, ''):
            return False
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    def _write_rows(self, rows):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        for row in rows:
            self.output.appendRow(row)
