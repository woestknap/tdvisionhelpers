"""TouchDesigner extension for the Phase 2C velocity component."""

import math
import time


class VelocityExt:
    """Calculate image-space center velocity for one selected object."""

    INPUT_HEADER = (
        'source_type', 'id', 'class_id', 'class_name', 'confidence',
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
        'depth_raw', 'source_frame', 'source_seq', 'video_frame',
    )
    HEADER = INPUT_HEADER + ('velocity_x', 'velocity_y', 'speed')

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')
        self._identity = None
        self._last_center = None
        self._last_sample_signature = None
        self._last_sample_time = None
        self._last_velocity = (0.0, 0.0, 0.0)
        self._has_written_output = False
        self._output_has_row = False

    def Update(self, force=False):
        """Process one new current sample, or reset for unavailable input."""
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

    def _read_current_row(self, input_dat):
        """Return a valid full-schema selected row, otherwise None."""
        if input_dat is None:
            return None
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.INPUT_HEADER
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
        center_x = self._finite_number(row['center_x'])
        center_y = self._finite_number(row['center_y'])
        if center_x is None or center_y is None:
            return None
        row['_center'] = (center_x, center_y)
        return row

    def _process_valid_row(self, row, now):
        """Return (output_row, is_new_sample); core timing accepts explicit now."""
        identity = (row['source_type'], row['id'])
        signature = tuple(row[column] for column in self.INPUT_HEADER)
        if signature == self._last_sample_signature:
            return self._output_row(row, self._last_velocity), False

        current_center = row['_center']
        if identity != self._identity or self._last_center is None:
            velocity = (0.0, 0.0, 0.0)
        else:
            dt = self._elapsed_seconds(now, self._last_sample_time)
            velocity = self._calculate_velocity(
                self._last_center, current_center, dt)

        self._identity = identity
        self._last_center = current_center
        self._last_sample_signature = signature
        self._last_sample_time = now
        self._last_velocity = velocity
        return self._output_row(row, velocity), True

    @staticmethod
    def _elapsed_seconds(now, previous):
        if previous is None:
            return None
        try:
            delta = float(now) - float(previous)
        except (TypeError, ValueError):
            return None
        return delta if math.isfinite(delta) and delta > 0.0 else None

    @staticmethod
    def _calculate_velocity(previous, current, dt):
        """Return zero for unsafe timing; otherwise normalized units per second."""
        if dt is None:
            return (0.0, 0.0, 0.0)
        velocity_x = (current[0] - previous[0]) / dt
        velocity_y = (current[1] - previous[1]) / dt
        speed = math.hypot(velocity_x, velocity_y)
        if not all(math.isfinite(value) for value in (velocity_x, velocity_y, speed)):
            return (0.0, 0.0, 0.0)
        return (velocity_x, velocity_y, speed)

    def _output_row(self, row, velocity):
        return tuple(row[column] for column in self.INPUT_HEADER) + tuple(
            self._format_number(value) for value in velocity)

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
        self._last_center = None
        self._last_sample_signature = None
        self._last_sample_time = None
        self._last_velocity = (0.0, 0.0, 0.0)

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
