"""TouchDesigner extension for the Phase 2C velocity component."""

import math
import time


class VelocityExt:
    """Calculate image-space center velocity for current canonical objects."""

    INPUT_HEADER = (
        'source_type', 'id', 'class_id', 'class_name', 'confidence',
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
        'depth_raw', 'source_frame', 'source_seq', 'video_frame',
    )
    HEADER = INPUT_HEADER + ('velocity_x', 'velocity_y', 'speed')

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')
        self._states = {}
        self._has_written_output = False
        self._output_has_rows = False

    def Update(self, force=False):
        """Process current valid rows, or reset for unavailable input."""
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

    def _read_current_rows(self, input_dat):
        """Return all valid rows; None denotes missing or malformed schema."""
        if input_dat is None:
            return None
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.INPUT_HEADER
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
            center_x = self._finite_number(row['center_x'])
            center_y = self._finite_number(row['center_y'])
            if center_x is None or center_y is None:
                continue
            row['_center'] = (center_x, center_y)
            rows.append(row)
        return rows

    def _process_valid_row(self, row, now):
        """Return (output_row, is_new_sample) for one canonical identity."""
        identity = (row['source_type'], row['id'])
        signature = tuple(row[column] for column in self.INPUT_HEADER)
        state = self._states.get(identity)
        if state is not None and signature == state['signature']:
            return self._output_row(row, state['velocity']), False

        current_center = row['_center']
        if state is None:
            velocity = (0.0, 0.0, 0.0)
        else:
            dt = self._elapsed_seconds(now, state['time'])
            velocity = self._calculate_velocity(
                state['center'], current_center, dt)

        self._states[identity] = {
            'center': current_center,
            'signature': signature,
            'time': now,
            'velocity': velocity,
        }
        return self._output_row(row, velocity), True

    def _remove_absent_states(self, current_identities):
        """Discard baseline state for identities absent from valid current rows."""
        removed = False
        for identity in tuple(self._states):
            if identity not in current_identities:
                del self._states[identity]
                removed = True
        return removed

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
