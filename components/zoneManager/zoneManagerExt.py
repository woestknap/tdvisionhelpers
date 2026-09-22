"""TouchDesigner extension for the Phase 4C multi-object zoneManager."""

import math


class ZoneManagerExt:
    """Generate independent rectangular-zone events for current objects."""

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
        self._states = {}
        self._previous_order = ()
        self._last_signature = None
        self._clear_events = False
        self._has_written_output = False

    def Update(self, force=False):
        """Advance all identity/zone states once per changed logical snapshot."""
        if self.output is None:
            return

        zones = self._read_zones(self._configured_op('Zonesdat'))
        if zones is None:
            self._reset_all()
            self._write_header()
            return

        zone_signature = tuple(zones)
        object_kind, rows = self._read_objects(self._configured_op('Inputdat'))
        if object_kind == 'invalid':
            self._process_invalid_input(zones, zone_signature, force)
        elif object_kind == 'loss':
            self._process_loss(zones, zone_signature, force)
        else:
            self._process_objects(rows, zones, zone_signature, force)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _read_objects(self, input_dat):
        """Return ('objects', rows), ('loss', ()), or ('invalid', ())."""
        if input_dat is None:
            return 'invalid', ()
        try:
            headers = [cell.val for cell in input_dat.row(0)]
            indices = {column: headers.index(column) for column in self.INPUT_HEADER}
            num_rows = input_dat.numRows
        except Exception:
            return 'invalid', ()
        if num_rows < 2:
            return 'loss', ()

        rows = []
        for row_index in range(1, num_rows):
            try:
                row = {
                    column: input_dat[row_index, index].val
                    for column, index in indices.items()
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
        return 'objects', rows

    def _read_zones(self, zones_dat):
        """Read valid unique rectangles in first-valid-occurrence order."""
        if zones_dat is None:
            return None
        try:
            headers = [cell.val for cell in zones_dat.row(0)]
            indices = {column: headers.index(column) for column in self.ZONE_HEADER}
            num_rows = zones_dat.numRows
        except Exception:
            return None

        zones = []
        names = set()
        for row_index in range(1, num_rows):
            try:
                name = zones_dat[row_index, indices['name']].val
                coordinates = tuple(
                    self._finite_number(zones_dat[row_index, indices[column]].val)
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

    def _process_objects(self, rows, zones, zone_signature, force):
        row_signatures = tuple(
            tuple(row[column] for column in self.INPUT_HEADER) for row in rows)
        signature = ('objects', row_signatures, zone_signature)
        if signature == self._last_signature:
            self._clear_event_pulse(rows, zones, force)
            return

        self._retain_zone_history(zones)
        current_identities = set()
        current_order = []
        normal_rows = []
        for row in rows:
            identity = (row['source_type'], row['id'])
            current_identities.add(identity)
            current_order.append(identity)
            state = self._states.get(identity)
            if state is None:
                state = {'occupancy': {}}
                self._states[identity] = state
            occupancy = state['occupancy']
            for name, x1, y1, x2, y2 in zones:
                inside = x1 <= row['_center'][0] <= x2 and y1 <= row['_center'][1] <= y2
                previous = occupancy.get(name, False)
                entered = inside and not previous
                exited = previous and not inside
                occupancy[name] = inside
                normal_rows.append((
                    name, int(inside), int(entered), int(exited), identity[0], identity[1]))

        disappearance_rows = self._remove_absent_states(current_identities, zones)
        self._previous_order = tuple(current_order)
        self._last_signature = signature
        rows_to_write = normal_rows + disappearance_rows
        self._clear_events = any(row[2] or row[3] for row in rows_to_write)
        self._write_rows(rows_to_write)

    def _process_loss(self, zones, zone_signature, force):
        signature = ('loss', zone_signature)
        if signature == self._last_signature:
            if self._clear_events:
                self._clear_events = False
                self._write_rows(self._zero_rows(zones))
            elif force:
                self._write_rows(self._zero_rows(zones))
            return

        self._retain_zone_history(zones)
        exit_rows = self._remove_absent_states(set(), zones)
        self._previous_order = ()
        self._last_signature = signature
        self._clear_events = bool(exit_rows)
        self._write_rows(exit_rows if exit_rows else self._zero_rows(zones))

    def _process_invalid_input(self, zones, zone_signature, force):
        signature = ('invalid', zone_signature)
        if force or signature != self._last_signature or not self._has_written_output:
            self._clear_object_state()
            self._last_signature = signature
            self._clear_events = False
            self._write_rows(self._zero_rows(zones))

    def _clear_event_pulse(self, rows, zones, force):
        if self._clear_events:
            self._clear_events = False
            self._write_rows(self._settled_rows(rows, zones))
        elif force:
            self._write_rows(self._settled_rows(rows, zones))

    def _retain_zone_history(self, zones):
        valid_names = {zone[0] for zone in zones}
        for state in self._states.values():
            occupancy = state['occupancy']
            for name in tuple(occupancy):
                if name not in valid_names:
                    del occupancy[name]
            for name in valid_names:
                occupancy.setdefault(name, False)

    def _remove_absent_states(self, current_identities, zones):
        """Append one exit per occupied still-valid zone, then discard its state."""
        rows = []
        ordered = []
        seen = set()
        for identity in self._previous_order:
            if identity in self._states and identity not in seen:
                ordered.append(identity)
                seen.add(identity)
        for identity in self._states:
            if identity not in seen:
                ordered.append(identity)
                seen.add(identity)
        for identity in ordered:
            if identity in current_identities:
                continue
            occupancy = self._states[identity]['occupancy']
            for name, _, _, _, _ in zones:
                if occupancy.get(name, False):
                    rows.append((name, 0, 0, 1, identity[0], identity[1]))
            del self._states[identity]
        return rows

    def _settled_rows(self, rows, zones):
        output_rows = []
        for row in rows:
            identity = (row['source_type'], row['id'])
            occupancy = self._states.get(identity, {}).get('occupancy', {})
            for name, _, _, _, _ in zones:
                output_rows.append((
                    name, int(occupancy.get(name, False)), 0, 0, identity[0], identity[1]))
        return output_rows

    @staticmethod
    def _zero_rows(zones):
        return [(name, 0, 0, 0, '', '') for name, _, _, _, _ in zones]

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
        self._states.clear()
        self._previous_order = ()

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
