"""TouchDesigner extension for the Phase 2B smoother component."""

import math
import time


class SmootherExt:
    """Time-based smoothing for one selected canonical object's geometry."""

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
        self._identity = None
        self._smoothed_geometry = None
        self._last_sample_signature = None
        self._last_sample_time = None
        self._has_written_output = False
        self._output_has_row = False

    def Update(self, force=False):
        """Process the current selected row, or reset on unavailable input."""
        if self.output is None:
            return

        row = self._read_current_row(self._configured_op('Inputdat'))
        if row is None:
            self._reset()
            if force or self._output_has_row or not self._has_written_output:
                self._write_header()
            return

        output_row, is_new_sample = self._process_valid_row(
            row, self._runtime_seconds())
        if force or is_new_sample or not self._has_written_output:
            self._write_row(output_row)

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

    def _read_current_row(self, input_dat):
        """Return one complete valid input row, otherwise None."""
        if input_dat is None:
            return None
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.HEADER
            }
            if input_dat.numRows < 2:
                return None
            row = {
                column: input_dat[1, index].val
                for column, index in column_indices.items()
            }
        except Exception:
            return None

        if row['source_type'] in (None, '') or row['id'] in (None, ''):
            return None
        geometry = tuple(self._finite_number(row[column]) for column in self.GEOMETRY_COLUMNS)
        if any(value is None for value in geometry):
            return None
        row['_geometry'] = geometry
        return row

    def _process_valid_row(self, row, now):
        """Return (output_row, is_new_sample); state math accepts explicit now."""
        identity = (row['source_type'], row['id'])
        signature = tuple(row[column] for column in self.HEADER)
        if signature == self._last_sample_signature:
            return self._output_row(row, self._smoothed_geometry), False

        current = row['_geometry']
        if identity != self._identity or self._smoothed_geometry is None:
            smoothed = current
        else:
            dt = self._elapsed_seconds(now, self._last_sample_time)
            smoothed = self._apply_smoothing(
                self._smoothed_geometry, current, self._smooth_time(), dt)

        self._identity = identity
        self._smoothed_geometry = smoothed
        self._last_sample_signature = signature
        self._last_sample_time = now
        return self._output_row(row, smoothed), True

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
        self._identity = None
        self._smoothed_geometry = None
        self._last_sample_signature = None
        self._last_sample_time = None

    def _write_header(self):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        self._has_written_output = True
        self._output_has_row = False

    def _write_row(self, row):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        self.output.appendRow(row)
        self._has_written_output = True
        self._output_has_row = True
