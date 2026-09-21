"""TouchDesigner extension for the Phase 3A zoneManager component."""

import math


class ZoneManagerExt:
    """Generate rectangular-zone occupancy and enter/exit events."""

    INPUT_HEADER = (
        'source_type', 'id', 'class_id', 'class_name', 'confidence',
        'center_x', 'center_y', 'width', 'height', 'x1', 'y1', 'x2', 'y2',
        'depth_raw', 'source_frame', 'source_seq', 'video_frame',
    )
    ZONE_HEADER = ('name', 'x1', 'y1', 'x2', 'y2')
    HEADER = ('zone', 'inside', 'entered', 'exited', 'source_type', 'id')

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.output = ownerComp.op('output')
        self._identity = None
        self._pending_identity = False
        self._occupancy = {}
        self._last_signature = None
        self._clear_events = False
        self._has_written_output = False

    def Update(self, force=False):
        """Advance zone state once per changed object or zone-table state."""
        if self.output is None:
            return

        zones = self._read_zones(self._configured_op('Zonesdat'))
        if zones is None:
            self._reset_all()
            self._write_header()
            return

        zone_signature = tuple(zones)
        object_kind, row = self._read_object(self._configured_op('Inputdat'))
        if object_kind == 'invalid':
            signature = ('invalid', zone_signature)
            if force or signature != self._last_signature or not self._has_written_output:
                self._clear_object_state()
                self._last_signature = signature
                self._clear_events = False
                self._write_rows(self._zero_rows(zones))
            return

        if object_kind == 'loss':
            self._process_loss(zones, zone_signature, force)
            return

        self._process_object(row, zones, zone_signature, force)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _read_object(self, input_dat):
        """Return ('object', row), ('loss', None), or ('invalid', None)."""
        if input_dat is None:
            return 'invalid', None
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.INPUT_HEADER
            }
            if input_dat.numRows < 2:
                return 'loss', None
            row = {
                column: input_dat[1, index].val
                for column, index in column_indices.items()
            }
        except Exception:
            return 'invalid', None

        if row['source_type'] in (None, '') or row['id'] in (None, ''):
            return 'invalid', None
        center_x = self._finite_number(row['center_x'])
        center_y = self._finite_number(row['center_y'])
        if center_x is None or center_y is None:
            return 'invalid', None
        row['_center'] = (center_x, center_y)
        return 'object', row

    def _read_zones(self, zones_dat):
        """Read valid unique rectangles in first-valid-occurrence order."""
        if zones_dat is None:
            return None
        try:
            headers = [cell.val for cell in zones_dat.row(0)]
            column_indices = {
                column: headers.index(column) for column in self.ZONE_HEADER
            }
            num_rows = zones_dat.numRows
        except Exception:
            return None

        zones = []
        names = set()
        for row_index in range(1, num_rows):
            try:
                name = zones_dat[row_index, column_indices['name']].val
                coordinates = tuple(
                    self._finite_number(zones_dat[row_index, column_indices[column]].val)
                    for column in ('x1', 'y1', 'x2', 'y2'))
            except Exception:
                continue
            if name in (None, '') or name in names or any(value is None for value in coordinates):
                continue
            x1, y1, x2, y2 = coordinates
            if x1 > x2 or y1 > y2:
                continue
            names.add(name)
            zones.append((name, x1, y1, x2, y2))
        return tuple(zones)

    def _process_object(self, row, zones, zone_signature, force):
        identity = (row['source_type'], row['id'])
        signature = ('object', tuple(row[column] for column in self.INPUT_HEADER), zone_signature)
        if signature == self._last_signature:
            self._clear_event_pulse(zones, force)
            return

        self._retain_zone_history(zones)
        if self._identity is not None and identity != self._identity:
            rows = self._identity_change_rows(zones)
            self._identity = identity
            self._pending_identity = True
            self._occupancy = {zone[0]: False for zone in zones}
        else:
            first_sample = self._identity is None or self._pending_identity
            self._identity = identity
            self._pending_identity = False
            rows = self._occupancy_rows(zones, row['_center'], identity, first_sample)

        self._last_signature = signature
        self._clear_events = any(row_values[2] or row_values[3] for row_values in rows)
        self._write_rows(rows)

    def _process_loss(self, zones, zone_signature, force):
        signature = ('loss', zone_signature)
        if signature == self._last_signature:
            self._clear_event_pulse(zones, force)
            return

        self._retain_zone_history(zones)
        rows = self._loss_rows(zones)
        self._clear_object_state()
        self._last_signature = signature
        self._clear_events = any(row_values[3] for row_values in rows)
        self._write_rows(rows)

    def _clear_event_pulse(self, zones, force):
        if self._clear_events:
            self._clear_events = False
            self._write_rows(self._settled_rows(zones))
        elif force:
            self._write_rows(self._settled_rows(zones))

    def _retain_zone_history(self, zones):
        self._occupancy = {
            zone[0]: self._occupancy.get(zone[0], False)
            for zone in zones
        }

    def _occupancy_rows(self, zones, center, identity, first_sample):
        rows = []
        for name, x1, y1, x2, y2 in zones:
            inside = x1 <= center[0] <= x2 and y1 <= center[1] <= y2
            previous = self._occupancy.get(name, False)
            entered = inside and (first_sample or not previous)
            exited = previous and not inside
            self._occupancy[name] = inside
            rows.append((name, int(inside), int(entered), int(exited), identity[0], identity[1]))
        return rows

    def _identity_change_rows(self, zones):
        previous_identity = self._identity
        rows = []
        for name, _, _, _, _ in zones:
            was_inside = self._occupancy.get(name, False)
            rows.append((
                name, 0, 0, int(was_inside),
                previous_identity[0] if was_inside else '',
                previous_identity[1] if was_inside else '',
            ))
        return rows

    def _loss_rows(self, zones):
        rows = []
        for name, _, _, _, _ in zones:
            was_inside = self._occupancy.get(name, False)
            rows.append((
                name, 0, 0, int(was_inside),
                self._identity[0] if was_inside else '',
                self._identity[1] if was_inside else '',
            ))
        return rows

    def _settled_rows(self, zones):
        identity = self._identity if self._identity is not None and not self._pending_identity else None
        return [
            (name, int(self._occupancy.get(name, False)), 0, 0,
             identity[0] if identity is not None else '',
             identity[1] if identity is not None else '')
            for name, _, _, _, _ in zones
        ]

    @staticmethod
    def _zero_rows(zones):
        return [
            (name, 0, 0, 0, '', '')
            for name, _, _, _, _ in zones
        ]

    @staticmethod
    def _finite_number(value):
        if value in (None, ''):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _clear_object_state(self):
        self._identity = None
        self._pending_identity = False
        self._occupancy = {}

    def _reset_all(self):
        self._clear_object_state()
        self._last_signature = None
        self._clear_events = False

    def _write_header(self):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        self._has_written_output = True

    def _write_rows(self, rows):
        self.output.clear()
        self.output.appendRow(self.HEADER)
        for row in rows:
            self.output.appendRow(row)
        self._has_written_output = True
