"""TouchDesigner extension for the Phase 1A yoloData adapter.

Attach this extension to a Base COMP containing a Table DAT named ``output``.
The COMP needs an OP parameter named ``Source`` that points to the
yolo-touchdesigner ``predictions`` DAT.  ``Classmap`` is an optional OP
parameter pointing to a Table DAT with ``class_id`` and ``class_name`` columns.
"""

import json
import math


class YoloDataExt:
    """Convert current yolo-touchdesigner object JSON into canonical rows."""

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
        'source_frame',
        'source_seq',
        'video_frame',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')

        self._source_dat = None
        self._source_text = None
        self._class_map_dat = None
        self._class_map_cook_count = None
        self._class_names = {}
        self._has_written_output = False

    def Update(self, force=False):
        """Write the current object-detection records to the output Table DAT.

        This is safe to call each frame: source JSON is only reparsed when the
        source DAT text changes, unless ``force`` is requested.
        """
        if self.output is None:
            return

        source_dat = self._configured_op('Source')
        class_map_dat = self._configured_op('Classmap')
        class_map_changed = self._refresh_class_map(class_map_dat)

        source_text = self._read_source_text(source_dat)
        source_changed = (
            source_dat is not self._source_dat
            or source_text != self._source_text
        )
        if not force and self._has_written_output and not source_changed and not class_map_changed:
            return

        self._source_dat = source_dat
        self._source_text = source_text
        message = self._read_message(source_text)
        rows = self._rows_from_message(message)
        self._write_rows(rows)
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
    def _cook_count(dat):
        if dat is None:
            return None
        try:
            return dat.cookCount
        except Exception:
            return None

    @staticmethod
    def _read_source_text(source_dat):
        if source_dat is None:
            return ''
        try:
            return source_dat.text
        except Exception:
            return ''

    @staticmethod
    def _read_message(source_text):
        try:
            message = json.loads(source_text)
        except Exception:
            return None
        return message if isinstance(message, dict) else None

    def _refresh_class_map(self, class_map_dat):
        cook_count = self._cook_count(class_map_dat)
        if (
            class_map_dat is self._class_map_dat
            and cook_count == self._class_map_cook_count
        ):
            return False

        self._class_map_dat = class_map_dat
        self._class_map_cook_count = cook_count
        self._class_names = {}
        if class_map_dat is None:
            return True
        try:
            num_rows = class_map_dat.numRows
        except Exception:
            return True
        if num_rows < 2:
            return True

        try:
            headers = [cell.val for cell in class_map_dat.row(0)]
            class_id_index = headers.index('class_id')
            class_name_index = headers.index('class_name')
        except Exception:
            return True

        for row_index in range(1, num_rows):
            try:
                class_id = class_map_dat[row_index, class_id_index].val
                class_name = class_map_dat[row_index, class_name_index].val
            except Exception:
                continue
            if class_id:
                self._class_names[str(class_id)] = class_name
        return True

    def _rows_from_message(self, message):
        if not message:
            return []

        message_type = message.get('type')
        if message_type == 'yolo':
            detections = message.get('predictions')
        elif message_type == 'yolo_combined':
            detections = message.get('yolo')
        else:
            return []

        if not isinstance(detections, list):
            return []

        source_frame = message.get('frame', '')
        source_seq = message.get('seq', '')
        video_frame = message.get('videoFrame', '')
        rows = []
        for detection in detections:
            row = self._canonical_row(
                detection,
                source_frame,
                source_seq,
                video_frame,
            )
            if row is not None:
                rows.append(row)
        return rows

    def _canonical_row(self, detection, source_frame, source_seq, video_frame):
        if not isinstance(detection, dict):
            return None

        category_name = detection.get('categoryName')
        if not isinstance(category_name, (list, tuple)) or not category_name:
            return None

        class_id = category_name[0]
        detection_id = detection.get('id')
        if detection_id is None or class_id is None:
            return None

        values = self._finite_values(
            detection.get('tx'),
            detection.get('ty'),
            detection.get('width'),
            detection.get('height'),
            detection.get('score'),
        )
        if values is None:
            return None
        center_x, center_y, width, height, confidence = values

        x1 = center_x - width * 0.5
        y1 = center_y - height * 0.5
        x2 = center_x + width * 0.5
        y2 = center_y + height * 0.5
        if not self._valid_normalized_box(center_x, center_y, width, height, x1, y1, x2, y2):
            return None

        class_id_text = str(class_id)
        return (
            'object',
            detection_id,
            class_id,
            self._class_names.get(class_id_text, ''),
            confidence,
            center_x,
            center_y,
            width,
            height,
            x1,
            y1,
            x2,
            y2,
            source_frame,
            source_seq,
            video_frame,
        )

    @staticmethod
    def _finite_values(*values):
        try:
            numeric_values = tuple(float(value) for value in values)
        except (TypeError, ValueError):
            return None
        return numeric_values if all(math.isfinite(value) for value in numeric_values) else None

    @staticmethod
    def _valid_normalized_box(center_x, center_y, width, height, x1, y1, x2, y2):
        return (
            0.0 <= center_x <= 1.0
            and 0.0 <= center_y <= 1.0
            and 0.0 <= width <= 1.0
            and 0.0 <= height <= 1.0
            and 0.0 <= x1 <= x2 <= 1.0
            and 0.0 <= y1 <= y2 <= 1.0
        )

    def _write_rows(self, rows):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        for row in rows:
            self.output.appendRow(row)
