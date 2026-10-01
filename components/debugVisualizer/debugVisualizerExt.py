"""TouchDesigner extension for the Phase 5 multi-object debugVisualizer controller."""

import math


class DebugVisualizerExt:
    """Prepare multi-object and aggregated-zone DATs for native TD rendering."""

    OBJECT_INPUT_HEADER = (
        'source_type', 'id', 'class_id', 'class_name', 'confidence',
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
        'depth_raw', 'source_frame', 'source_seq', 'video_frame',
    )
    VELOCITY_INPUT_HEADER = OBJECT_INPUT_HEADER + (
        'velocity_x', 'velocity_y', 'speed',
    )
    ZONE_DEFINITION_HEADER = ('name', 'x1', 'y1', 'x2', 'y2')
    ZONE_STATE_HEADER = ('zone', 'inside', 'entered', 'exited', 'source_type', 'id')
    OBJECT_HEADER = (
        'source_type', 'id', 'class_name', 'confidence', 'depth_raw',
        'center_x', 'center_y', 'x1', 'y1', 'x2', 'y2',
        'velocity_x', 'velocity_y', 'velocity_end_x', 'velocity_end_y',
        'speed', 'label',
    )
    ZONE_HEADER = ('zone', 'x1', 'y1', 'x2', 'y2', 'inside', 'entered', 'exited')
    VELOCITY_VISUAL_SCALE = 0.15

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.objectData = ownerComp.op('objectData')
        self.zoneData = ownerComp.op('zoneData')
        self._zone_label_replicator = ownerComp.op('zoneLabelReplicator')
        self._source_image = ownerComp.op('sourceImage')

    def Update(self, force=False):
        """Reflect current valid inputs; no event or object state is retained."""
        object_rows = self._read_objects(self._configured_op('Objectdat'))
        velocity_by_identity = self._read_velocities(self._configured_op('Velocitydat'))
        zones = self._read_zones(self._configured_op('Zonedefdat'))
        states = self._read_zone_states(self._configured_op('Zonestatedat'))

        if self.objectData is not None:
            self._write_objects(object_rows, velocity_by_identity)
        if self.zoneData is not None:
            self._write_zones(zones, states)
            self._update_zone_labels(zones)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _read_objects(self, dat):
        """Return every current valid canonical object row in DAT order."""
        rows = self._read_rows(dat, self.OBJECT_INPUT_HEADER)
        if rows is None:
            return ()
        valid_rows = []
        for row in rows:
            if row['source_type'] in (None, '') or row['id'] in (None, ''):
                continue
            geometry = tuple(
                self._finite_number(row[column])
                for column in ('center_x', 'center_y', 'x1', 'y1', 'x2', 'y2')
            )
            if any(value is None for value in geometry):
                continue
            row['_center'] = geometry[:2]
            valid_rows.append(row)
        return valid_rows

    def _read_velocities(self, dat):
        """Return first valid velocity rows keyed by canonical identity."""
        rows = self._read_rows(dat, self.VELOCITY_INPUT_HEADER)
        if rows is None:
            return {}
        velocities = {}
        for row in rows:
            identity = (row['source_type'], row['id'])
            if identity[0] in (None, '') or identity[1] in (None, '') or identity in velocities:
                continue
            values = tuple(
                self._finite_number(row[column])
                for column in ('velocity_x', 'velocity_y', 'speed')
            )
            if any(value is None for value in values):
                continue
            row['_velocity'] = values
            velocities[identity] = row
        return velocities

    def _read_zones(self, dat):
        if dat is None:
            return None
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {
                column: headers.index(column) for column in self.ZONE_DEFINITION_HEADER
            }
            num_rows = dat.numRows
        except Exception:
            return None

        zones = []
        names = set()
        for row_index in range(1, num_rows):
            try:
                name = dat[row_index, indices['name']].val
                coordinates = tuple(
                    self._finite_number(dat[row_index, indices[column]].val)
                    for column in ('x1', 'y1', 'x2', 'y2')
                )
            except Exception:
                continue
            if name in (None, '') or name in names or any(value is None for value in coordinates):
                continue
            x1, y1, x2, y2 = coordinates
            if x1 > x2 or y1 > y2:
                continue
            names.add(name)
            zones.append((name, x1, y1, x2, y2))
        return zones

    def _read_zone_states(self, dat):
        if dat is None:
            return {}
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {
                column: headers.index(column) for column in self.ZONE_STATE_HEADER
            }
            num_rows = dat.numRows
        except Exception:
            return {}

        state_groups = {}
        for row_index in range(1, num_rows):
            try:
                name = dat[row_index, indices['zone']].val
                flags = tuple(
                    self._state_flag(dat[row_index, indices[column]].val)
                    for column in ('inside', 'entered', 'exited')
                )
            except Exception:
                continue
            source_type = dat[row_index, indices['source_type']].val
            source_id = dat[row_index, indices['id']].val
            if name in (None, '') or any(value is None for value in flags):
                continue
            if source_type in (None, '') and source_id in (None, ''):
                group = 'legacy'
            elif source_type not in (None, '') and source_id not in (None, ''):
                group = 'identified'
            else:
                continue
            grouped = state_groups.setdefault(name, {
                'identified': [0, 0, 0], 'legacy': [0, 0, 0],
                'identified_present': False,
            })
            if group == 'identified':
                grouped['identified_present'] = True
            for index, flag in enumerate(flags):
                grouped[group][index] = int(bool(grouped[group][index] or flag))

        states = {}
        for name, grouped in state_groups.items():
            states[name] = tuple(
                grouped['identified'] if grouped['identified_present'] else grouped['legacy'])
        return states

    @staticmethod
    def _read_rows(dat, required_columns):
        if dat is None:
            return None
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {column: headers.index(column) for column in required_columns}
            return [
                {column: dat[row_index, index].val for column, index in indices.items()}
                for row_index in range(1, dat.numRows)
            ]
        except Exception:
            return None

    def _write_objects(self, object_rows, velocity_by_identity):
        self.objectData.clear()
        self.objectData.appendRow(self.OBJECT_HEADER)
        for object_row in object_rows:
            velocity_row = velocity_by_identity.get(
                (object_row['source_type'], object_row['id']))
            velocity_fields = ('', '', '', '', '')
            if velocity_row is not None:
                velocity_x, velocity_y, _ = velocity_row['_velocity']
                velocity_fields = (
                    velocity_row['velocity_x'], velocity_row['velocity_y'],
                    self._format_number(object_row['_center'][0] + velocity_x * self.VELOCITY_VISUAL_SCALE),
                    self._format_number(object_row['_center'][1] + velocity_y * self.VELOCITY_VISUAL_SCALE),
                    velocity_row['speed'],
                )
            class_name = object_row['class_name']
            label_prefix = class_name if class_name not in (None, '') else object_row['source_type']
            self.objectData.appendRow((
                object_row['source_type'], object_row['id'], class_name,
                object_row['confidence'], object_row['depth_raw'],
                object_row['center_x'], object_row['center_y'],
                object_row['x1'], object_row['y1'], object_row['x2'], object_row['y2'],
                *velocity_fields, '{} #{}'.format(label_prefix, object_row['id']),
            ))

    def _write_zones(self, zones, states):
        self.zoneData.clear()
        self.zoneData.appendRow(self.ZONE_HEADER)
        if zones is None:
            return
        for name, x1, y1, x2, y2 in zones:
            inside, entered, exited = states.get(name, (0, 0, 0))
            self.zoneData.appendRow((
                name, self._format_number(x1), self._format_number(y1),
                self._format_number(x2), self._format_number(y2),
                inside, entered, exited,
            ))

    def _update_zone_labels(self, zones):
        """Update existing replicated zone labels from current valid definitions."""
        if not zones:
            return
        if self._zone_label_replicator is None:
            self._zone_label_replicator = self.ownerComp.op('zoneLabelReplicator')
        if self._source_image is None:
            self._source_image = self.ownerComp.op('sourceImage')
        if self._zone_label_replicator is None or self._source_image is None:
            return

        try:
            width = float(self._source_image.width)
            height = float(self._source_image.height)
        except Exception:
            return
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            return

        for name, x1, y1, x2, y2 in zones:
            try:
                replica = self.ownerComp.op(name)
                text_top = replica.op('text1') if replica is not None else None
                if text_top is None:
                    continue
                text_top.par.text = name.upper()
                text_top.par.positionx = x1 * width + 8
                text_top.par.positiony = -(1.0 - y2) * height - 8
            except Exception:
                continue

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
    def _state_flag(value):
        number = DebugVisualizerExt._finite_number(value)
        return None if number is None else int(number != 0.0)

    @staticmethod
    def _format_number(value):
        return repr(float(value))
