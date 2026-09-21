"""TouchDesigner extension for the Phase 2A objectSelector component."""

import math


class ObjectSelectorExt:
    """Select at most one current Phase 1 fused object row."""

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
    MODES = (
        'id',
        'highest_confidence',
        'largest',
        'nearest',
        'center',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')
        self._input_dat = None
        self._input_text = None
        self._parameter_state = None
        self._has_written_output = False

    def Update(self, force=False):
        """Update the selected row when input text or selector settings change."""
        if self.output is None:
            return

        input_dat = self._configured_op('Inputdat')
        input_text = self._dat_text(input_dat)
        parameter_state = self._parameter_state_value()
        changed = (
            input_dat is not self._input_dat
            or input_text != self._input_text
            or parameter_state != self._parameter_state
        )
        if not force and self._has_written_output and not changed:
            return

        self._input_dat = input_dat
        self._input_text = input_text
        self._parameter_state = parameter_state

        candidates = self._read_candidates(input_dat)
        selected = self._select(candidates, parameter_state)
        self._write_selected(selected)
        self._has_written_output = True

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

    def _parameter_state_value(self):
        return (
            self._mode_value(self._parameter_value('Mode', 'highest_confidence')),
            str(self._parameter_value('Sourcetype', 'object')),
            self._parameter_value('Targetid', 0),
            bool(self._parameter_value('Filterclass', False)),
            self._parameter_value('Classid', 0),
            self._parameter_value('Targetx', 0.5),
            self._parameter_value('Targety', 0.5),
        )

    @staticmethod
    def _dat_text(dat):
        if dat is None:
            return ''
        try:
            return dat.text
        except Exception:
            return ''

    @staticmethod
    def _mode_value(value):
        mode = str(value).strip().lower().replace(' ', '_')
        return mode if mode in ObjectSelectorExt.MODES else 'highest_confidence'

    def _read_candidates(self, input_dat):
        if input_dat is None:
            return ()
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.HEADER
            }
            num_rows = input_dat.numRows
        except Exception:
            return ()

        candidates = []
        for row_index in range(1, num_rows):
            try:
                row = {
                    column: input_dat[row_index, index].val
                    for column, index in column_indices.items()
                }
            except Exception:
                continue
            if row['source_type'] == 'object' and row['id'] not in (None, ''):
                candidates.append(row)
        return candidates

    def _select(self, candidates, state):
        mode, source_type, target_id, filter_class, class_id, target_x, target_y = state
        if filter_class:
            candidates = [
                row for row in candidates
                if self._class_matches(row.get('class_id'), class_id)
            ]

        if mode == 'id':
            return self._select_id(candidates, source_type, target_id)
        if mode == 'highest_confidence':
            return self._select_by_numeric(candidates, 'confidence', highest=True)
        if mode == 'largest':
            return self._select_largest(candidates)
        if mode == 'nearest':
            return self._select_by_numeric(candidates, 'depth_raw', highest=False)
        if mode == 'center':
            return self._select_center(candidates, target_x, target_y)
        return None

    @staticmethod
    def _select_id(candidates, source_type, target_id):
        target_id_text = str(target_id)
        for row in candidates:
            if row['source_type'] == source_type and row['id'] == target_id_text:
                return row
        return None

    def _select_by_numeric(self, candidates, column, highest):
        selected = None
        selected_value = None
        for row in candidates:
            value = self._finite_number(row.get(column))
            if value is None:
                continue
            if (
                selected is None
                or (highest and value > selected_value)
                or (not highest and value < selected_value)
            ):
                selected = row
                selected_value = value
        return selected

    def _select_largest(self, candidates):
        selected = None
        selected_area = None
        for row in candidates:
            width = self._finite_number(row.get('width'))
            height = self._finite_number(row.get('height'))
            if width is None or height is None:
                continue
            area = width * height
            if selected is None or area > selected_area:
                selected = row
                selected_area = area
        return selected

    def _select_center(self, candidates, target_x, target_y):
        target_x = self._finite_number(target_x)
        target_y = self._finite_number(target_y)
        if target_x is None or target_y is None:
            return None

        selected = None
        selected_distance = None
        for row in candidates:
            center_x = self._finite_number(row.get('center_x'))
            center_y = self._finite_number(row.get('center_y'))
            if center_x is None or center_y is None:
                continue
            distance = (center_x - target_x) ** 2 + (center_y - target_y) ** 2
            if selected is None or distance < selected_distance:
                selected = row
                selected_distance = distance
        return selected

    @staticmethod
    def _class_matches(value, class_id):
        value_number = ObjectSelectorExt._finite_number(value)
        class_number = ObjectSelectorExt._finite_number(class_id)
        return value_number is not None and value_number == class_number

    @staticmethod
    def _finite_number(value):
        if value in (None, ''):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _write_selected(self, selected):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        if selected is not None:
            self.output.appendRow(tuple(selected[column] for column in self.HEADER))
