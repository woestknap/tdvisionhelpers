"""TouchDesigner extension for lightweight pose-transform stabilization."""

import math
import time


class TransformStabilizerExt:
    """Apply per-identity alpha-beta position filtering and short prediction."""

    HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'confidence', 'visible', 'source_frame', 'source_seq', 'video_frame',
    )
    MIN_DT_SECONDS = 1e-6

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.stabilizedTransformData = ownerComp.op('stabilizedTransformData')
        self._states = {}

    def Update(self, force=False):
        """Process current transforms and remove state for absent identities."""
        rows = self._read_rows(self._configured_op('Inputdat'))
        if rows is None:
            self._states.clear()
            self._write_rows(())
            return

        if not self._enabled():
            self._states.clear()
            self._write_rows(tuple(self._passthrough_row(row) for row in rows))
            return

        now = self._runtime_seconds()
        settings = self._settings()
        current_identities = set()
        output_rows = []
        for row in rows:
            identity = (row['source_type'], row['id'], row['anchor'])
            current_identities.add(identity)
            output_rows.append(self._process_row(row, identity, now, settings))
        self._remove_absent_states(current_identities)
        self._write_rows(output_rows)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _enabled(self):
        value = self._configured_op('Enabled')
        if isinstance(value, bool):
            return value
        number = self._finite_number(value)
        if number is not None:
            return number != 0.0
        if isinstance(value, str):
            return value.strip().lower() not in ('', '0', 'false', 'off', 'no')
        return True

    def _parameter_number(self, parameter_name, default, minimum=None, maximum=None):
        value = self._finite_number(self._configured_op(parameter_name))
        value = default if value is None else value
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def _settings(self):
        prediction_ms = self._parameter_number('Predictionms', 40.0, 0.0)
        max_prediction_ms = self._parameter_number('Maxpredictionms', 80.0, 0.0)
        return {
            'position_alpha': self._parameter_number('Positionalpha', 0.65, 0.0, 1.0),
            'position_beta': self._parameter_number('Positionbeta', 0.08, 0.0, 1.0),
            'scale_alpha': self._parameter_number('Scalealpha', 0.35, 0.0, 1.0),
            'rotation_alpha': self._parameter_number('Rotationalpha', 0.35, 0.0, 1.0),
            'prediction_seconds': min(prediction_ms, max_prediction_ms) / 1000.0,
            'max_gap_seconds': self._parameter_number('Maxgapms', 250.0, 0.0) / 1000.0,
        }

    def _read_rows(self, dat):
        if dat is None:
            return None
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {column: headers.index(column) for column in self.HEADER}
            num_rows = dat.numRows
        except Exception:
            return None

        rows = []
        for row_index in range(1, num_rows):
            try:
                row = {
                    column: dat[row_index, index].val
                    for column, index in indices.items()
                }
            except Exception:
                continue
            if (
                row['source_type'] in (None, '')
                or row['id'] in (None, '')
                or row['anchor'] in (None, '')
            ):
                continue
            rows.append(row)
        return rows

    def _process_row(self, row, identity, now, settings):
        measurement = self._measurement(row)
        source_visible = self._finite_number(row['visible'])
        if source_visible != 1.0 or measurement is None:
            self._states.pop(identity, None)
            return self._invisible_row(row)

        signature = self._measurement_signature(row)
        state = self._states.get(identity)
        if state is None:
            state = self._new_state(measurement, signature, now)
            self._states[identity] = state
        elif signature != state['signature']:
            elapsed = self._elapsed_seconds(now, state['measurement_time'])
            if elapsed is None or elapsed > settings['max_gap_seconds']:
                state = self._new_state(measurement, signature, now)
                self._states[identity] = state
            else:
                self._correct_measurement(state, measurement, signature, now, elapsed, settings)

        return self._predicted_row(row, state, now, settings['prediction_seconds'])

    def _new_state(self, measurement, signature, now):
        x, y, scale, rotation, _ = measurement
        return {
            'x': x, 'y': y, 'velocity_x': 0.0, 'velocity_y': 0.0,
            'scale': scale, 'rotation': self._normalize_angle(rotation),
            'signature': signature, 'measurement_time': now,
        }

    def _correct_measurement(self, state, measurement, signature, now, elapsed, settings):
        measurement_x, measurement_y, measurement_scale, measurement_rotation, _ = measurement
        predicted_x = state['x'] + state['velocity_x'] * elapsed
        predicted_y = state['y'] + state['velocity_y'] * elapsed
        residual_x = measurement_x - predicted_x
        residual_y = measurement_y - predicted_y
        state['x'] = predicted_x + settings['position_alpha'] * residual_x
        state['y'] = predicted_y + settings['position_alpha'] * residual_y
        if elapsed > self.MIN_DT_SECONDS:
            correction = settings['position_beta'] / elapsed
            state['velocity_x'] += correction * residual_x
            state['velocity_y'] += correction * residual_y

        state['scale'] += settings['scale_alpha'] * (measurement_scale - state['scale'])
        angle_delta = self._shortest_angle_delta(measurement_rotation, state['rotation'])
        state['rotation'] = self._normalize_angle(
            state['rotation'] + settings['rotation_alpha'] * angle_delta)
        state['signature'] = signature
        state['measurement_time'] = now

    def _predicted_row(self, row, state, now, prediction_seconds):
        elapsed = self._elapsed_seconds(now, state['measurement_time'])
        elapsed = 0.0 if elapsed is None else elapsed
        horizon = elapsed + prediction_seconds
        return (
            row['source_type'], row['id'], row['anchor'],
            state['x'] + state['velocity_x'] * horizon,
            state['y'] + state['velocity_y'] * horizon,
            state['scale'], state['rotation'], row['confidence'], 1,
            row['source_frame'], row['source_seq'], row['video_frame'],
        )

    def _passthrough_row(self, row):
        return tuple(row[column] for column in self.HEADER)

    def _invisible_row(self, row):
        return (
            row['source_type'], row['id'], row['anchor'],
            row['x'], row['y'], row['scale'], row['rotation'],
            row['confidence'], 0, row['source_frame'], row['source_seq'],
            row['video_frame'],
        )

    def _remove_absent_states(self, current_identities):
        for identity in tuple(self._states):
            if identity not in current_identities:
                del self._states[identity]

    @classmethod
    def _measurement(cls, row):
        values = tuple(cls._finite_number(row[column]) for column in (
            'x', 'y', 'scale', 'rotation', 'confidence'))
        return None if any(value is None for value in values) else values

    def _measurement_signature(self, row):
        return tuple(row[column] for column in (
            'x', 'y', 'scale', 'rotation', 'confidence', 'visible',
            'source_frame', 'source_seq', 'video_frame',
        ))

    def _write_rows(self, rows):
        if self.stabilizedTransformData is None:
            return
        self.stabilizedTransformData.clear()
        self.stabilizedTransformData.appendRow(self.HEADER)
        for row in rows:
            self.stabilizedTransformData.appendRow(row)

    @staticmethod
    def _elapsed_seconds(now, previous):
        try:
            delta = float(now) - float(previous)
        except (TypeError, ValueError):
            return None
        return delta if math.isfinite(delta) and delta > 0.0 else None

    @staticmethod
    def _shortest_angle_delta(target, current):
        return (target - current + 180.0) % 360.0 - 180.0

    @staticmethod
    def _normalize_angle(angle):
        return (angle + 180.0) % 360.0 - 180.0

    @staticmethod
    def _finite_number(value):
        if value in (None, '') or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _runtime_seconds():
        """Use TouchDesigner's clock when available, otherwise a monotonic clock."""
        try:
            return float(absTime.seconds)
        except Exception:
            return time.monotonic()
