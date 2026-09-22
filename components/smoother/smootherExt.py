"""TouchDesigner extension for the Phase 2B smoother component."""

import math
import time


class SmootherExt:
    """Time-based smoothing for current canonical object rows."""

    HEADER = (
        'source_type', 'id', 'class_id', 'class_name', 'confidence',
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
        'depth_raw', 'source_frame', 'source_seq', 'video_frame',
    )
    GEOMETRY_COLUMNS = (
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')
        self._states = {}
        self._has_written_output = False
        self._output_has_rows = False

    def Update(self, force=False):
        """Process current valid object rows, or reset on unavailable input."""
        if self.output is None:
            return

        rows = self._read_current_rows(self._configured_op('Inputdat'))
        if rows is None:
            self._reset()
            if force or self._output_has_rows or not self._has_written_output:
                self._write_header()
            return

        now = self._runtime_seconds()
        current_identities = set()
        output_rows = []
        changed = False
        for row in rows:
            identity = (row['source_type'], row['id'])
            current_identities.add(identity)
            output_row, is_new_sample = self._process_valid_row(row, now)
            output_rows.append(output_row)
            changed = changed or is_new_sample

        if self._remove_absent_states(current_identities):
            changed = True
        if force or changed or not self._has_written_output:
            self._write_rows(output_rows)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _smooth_time(self):
        parameter = getattr(self.ownerComp.par, 'Smoothtime', None)
        if parameter is None:
            return 0.15
        try:
            value = float(parameter.eval())
        except (TypeError, ValueError):
            return 0.15
        return value if math.isfinite(value) else 0.15

    def _read_current_rows(self, input_dat):
        """Return all valid rows; None denotes missing or malformed schema."""
        if input_dat is None:
            return None
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.HEADER
            }
            num_rows = input_dat.numRows
        except Exception:
            return None

        rows = []
        for row_index in range(1, num_rows):
            try:
                row = {
                    column: input_dat[row_index, index].val
                    for column, index in column_indices.items()
                }
            except Exception:
                continue
            if row['source_type'] in (None, '') or row['id'] in (None, ''):
                continue
            geometry = tuple(
                self._finite_number(row[column]) for column in self.GEOMETRY_COLUMNS)
            if any(value is None for value in geometry):
                continue
            row['_geometry'] = geometry
            rows.append(row)
        return rows

    def _process_valid_row(self, row, now):
        """Return (output_row, is_new_sample) for this canonical identity."""
        identity = (row['source_type'], row['id'])
        signature = tuple(row[column] for column in self.HEADER)
        state = self._states.get(identity)
        if state is not None and signature == state['signature']:
            return self._output_row(row, state['geometry']), False

        current = row['_geometry']
        if state is None:
            smoothed = current
        else:
            dt = self._elapsed_seconds(now, state['time'])
            smoothed = self._apply_smoothing(
                state['geometry'], current, self._smooth_time(), dt)

        self._states[identity] = {
            'geometry': smoothed,
            'signature': signature,
            'time': now,
        }
        return self._output_row(row, smoothed), True

    def _remove_absent_states(self, current_identities):
        """Discard state as soon as an identity is absent from valid input rows."""
        removed = False
        for identity in tuple(self._states):
            if identity not in current_identities:
                del self._states[identity]
                removed = True
        return removed

    @staticmethod
    def _elapsed_seconds(now, previous):
        """Use an immediate sample for an invalid/non-positive clock delta."""
        if previous is None:
            return None
        try:
            delta = float(now) - float(previous)
        except (TypeError, ValueError):
            return None
        return delta if math.isfinite(delta) and delta > 0.0 else None

    @staticmethod
    def _apply_smoothing(previous, current, smooth_time, dt):
        """Continuous-time exponential smoothing, with safe immediate fallback."""
        if smooth_time <= 0.0 or dt is None:
            return current
        alpha = 1.0 - math.exp(-dt / smooth_time)
        return tuple(old + alpha * (new - old) for old, new in zip(previous, current))

    def _output_row(self, row, geometry):
        values = dict(row)
        for column, value in zip(self.GEOMETRY_COLUMNS, geometry):
            values[column] = self._format_number(value)
        return tuple(values[column] for column in self.HEADER)

    @staticmethod
    def _finite_number(value):
        if value in (None, ''):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _format_number(value):
        """Shortest stable Python float spelling; pass-through fields are untouched."""
        return repr(float(value))

    @staticmethod
    def _runtime_seconds():
        """Prefer TouchDesigner's absolute runtime clock, with a Python fallback."""
        try:
            return float(absTime.seconds)
        except Exception:
            return time.monotonic()

    def _reset(self):
        self._states.clear()

    def _write_header(self):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        self._has_written_output = True
        self._output_has_rows = False

    def _write_rows(self, rows):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        for row in rows:
            self.output.appendRow(row)
        self._has_written_output = True
        self._output_has_rows = bool(rows)
