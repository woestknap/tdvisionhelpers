"""TouchDesigner extension for the stateless multi-row classFilter component."""


class ClassFilterExt:
    """Pass through canonical rows whose integer class IDs match a filter."""

    CANONICAL_HEADER = (
        'source_type', 'id', 'class_id', 'class_name', 'confidence',
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
        'depth_raw', 'source_frame', 'source_seq', 'video_frame',
    )
    MODES = ('include', 'exclude')

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')

    def Update(self, force=False):
        """Filter all current valid rows; no history is retained."""
        if self.output is None:
            return

        input_data = self._read_input(self._configured_op('Inputdat'))
        if input_data is None:
            self._write_rows(self.CANONICAL_HEADER, ())
            return

        headers, rows, class_index = input_data
        mode = self._mode_value(self._parameter_value('Mode', 'include'))
        class_ids = self._parse_class_ids(self._parameter_value('Classes', '0'))
        filtered_rows = []
        for row in rows:
            class_id = self._integer_class_id(row[class_index])
            if class_id is None:
                continue
            matches = class_id in class_ids
            if (mode == 'include' and matches) or (mode == 'exclude' and not matches):
                filtered_rows.append(row)
        self._write_rows(headers, filtered_rows)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _parameter_value(self, parameter_name, default):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return default
        try:
            return parameter.eval()
        except Exception:
            return default

    def _read_input(self, input_dat):
        """Return exact header/rows when the full canonical schema is present."""
        if input_dat is None:
            return None
        try:
            headers = tuple(cell.val for cell in input_dat.row(0))
            if not all(column in headers for column in self.CANONICAL_HEADER):
                return None
            class_index = headers.index('class_id')
            width = len(headers)
            rows = [
                tuple(input_dat[row_index, column_index].val for column_index in range(width))
                for row_index in range(1, input_dat.numRows)
            ]
        except Exception:
            return None
        return headers, rows, class_index

    @classmethod
    def _mode_value(cls, value):
        mode = str(value).strip().lower()
        return mode if mode in cls.MODES else 'include'

    @classmethod
    def _parse_class_ids(cls, value):
        class_ids = set()
        for item in str(value).split(','):
            class_id = cls._integer_class_id(item)
            if class_id is not None:
                class_ids.add(class_id)
        return class_ids

    @staticmethod
    def _integer_class_id(value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    def _write_rows(self, headers, rows):
        self.output.clear()
        self.output.appendRow(headers)
        for row in rows:
            self.output.appendRow(row)
