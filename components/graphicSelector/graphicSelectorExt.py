"""TouchDesigner extension for stable per-identity graphic-slot assignment."""

import math
import random


class GraphicSelectorExt:
    """Assign physical source slots without rendering or pose interpretation."""

    INPUT_HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'confidence', 'visible', 'source_frame', 'source_seq', 'video_frame',
    )
    SOURCES_HEADER = ('name', 'enabled', 'weight')
    OUTPUT_HEADER = (
        'source_type', 'id', 'graphic_index', 'graphic_name', 'visible',
        'source_frame', 'source_seq', 'video_frame',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.assignmentData = ownerComp.op('assignmentData')
        self._assignments = {}
        self._mode = None
        self._seed = None
        self._fixed_index = None
        self._round_robin_cursor = 0
        self._random = random.Random(1)
        self._reassign_requested = False

    def Update(self, force=False):
        """Reflect current identities while preserving valid slot assignments."""
        input_rows = self._read_rows(self._configured_op('Inputdat'), self.INPUT_HEADER)
        if input_rows is None:
            self._clear_assignments()
            self._write_rows(())
            return
        rows = [
            row for row in input_rows
            if row['source_type'] not in (None, '') and row['id'] not in (None, '')
        ]

        if not self._enabled():
            self._clear_assignments()
            self._write_rows(tuple(self._blank_row(row) for row in rows))
            return

        mode = self._mode_value()
        seed = self._integer_parameter('Seed', 1)
        fixed_index = self._integer_parameter('Fixedindex', 0)
        if self._configuration_changed(mode, seed, fixed_index):
            self._reset_assignment_run(mode, seed, fixed_index)
        elif self._reassign_requested:
            # Reassign starts new identity assignments but deliberately keeps
            # the component-local random generator at its current sequence.
            self._clear_assignments()
            self._reassign_requested = False

        sources = self._read_sources(self._configured_op('Sourcesdat'))
        current_identities = set()
        output_rows = []
        for row in rows:
            identity = (row['source_type'], row['id'])
            current_identities.add(identity)
            slot = self._slot_for_identity(identity, sources, mode, fixed_index)
            output_rows.append(self._assignment_row(row, slot, sources))
        self._remove_absent_assignments(current_identities)
        self._write_rows(output_rows)

    def Reassign(self):
        """Request a complete reassignment; call this from a Parameter Execute DAT."""
        self._clear_assignments()
        self._reassign_requested = True

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _mode_value(self):
        value = self._configured_op('Mode')
        value = value.strip().lower() if isinstance(value, str) else ''
        return value if value in ('fixed', 'round_robin', 'random') else 'random'

    def _integer_parameter(self, parameter_name, default):
        value = self._finite_number(self._configured_op(parameter_name))
        if value is None:
            return default
        return int(value)

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

    def _configuration_changed(self, mode, seed, fixed_index):
        return (mode, seed, fixed_index) != (self._mode, self._seed, self._fixed_index)

    def _reset_assignment_run(self, mode, seed, fixed_index):
        self._clear_assignments()
        self._mode = mode
        self._seed = seed
        self._fixed_index = fixed_index
        self._round_robin_cursor = 0
        self._random = random.Random(seed)
        self._reassign_requested = False

    def _clear_assignments(self):
        self._assignments.clear()
        self._round_robin_cursor = 0

    @staticmethod
    def _read_rows(dat, required_columns):
        if dat is None:
            return None
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {column: headers.index(column) for column in required_columns}
            return [
                {
                    column: dat[row_index, column_index].val
                    for column, column_index in indices.items()
                }
                for row_index in range(1, dat.numRows)
            ]
        except Exception:
            return None

    def _read_sources(self, dat):
        rows = self._read_rows(dat, self.SOURCES_HEADER)
        if rows is None:
            return {}
        sources = {}
        for physical_slot, row in enumerate(rows):
            name = row['name']
            weight = self._finite_number(row['weight'])
            if name in (None, '') or weight is None or weight < 0.0:
                continue
            sources[physical_slot] = {
                'name': name,
                'enabled': self._logical_value(row['enabled']),
                'weight': weight,
            }
        return sources

    def _slot_for_identity(self, identity, sources, mode, fixed_index):
        assigned_slot = self._assignments.get(identity)
        if assigned_slot is not None and self._slot_selectable(assigned_slot, sources, mode):
            return assigned_slot
        if assigned_slot is not None:
            del self._assignments[identity]

        slot = self._select_slot(sources, mode, fixed_index)
        if slot is not None:
            self._assignments[identity] = slot
        return slot

    def _select_slot(self, sources, mode, fixed_index):
        if mode == 'fixed':
            return fixed_index if self._slot_selectable(fixed_index, sources, mode) else None
        selectable = [
            slot for slot in sorted(sources)
            if self._slot_selectable(slot, sources, mode)
        ]
        if not selectable:
            return None
        if mode == 'round_robin':
            slot = selectable[self._round_robin_cursor % len(selectable)]
            self._round_robin_cursor += 1
            return slot
        return self._weighted_random_slot(selectable, sources)

    def _slot_selectable(self, slot, sources, mode):
        source = sources.get(slot)
        if source is None or not source['enabled']:
            return False
        return mode != 'random' or source['weight'] > 0.0

    def _weighted_random_slot(self, selectable, sources):
        total_weight = sum(sources[slot]['weight'] for slot in selectable)
        if total_weight <= 0.0:
            return None
        target = self._random.random() * total_weight
        running_weight = 0.0
        for slot in selectable:
            running_weight += sources[slot]['weight']
            if target < running_weight:
                return slot
        return selectable[-1]

    def _assignment_row(self, row, slot, sources):
        source = sources.get(slot) if slot is not None else None
        visible = int(self._logical_value(row['visible']) and source is not None)
        return (
            row['source_type'], row['id'],
            '' if source is None else slot,
            '' if source is None else source['name'],
            visible, row['source_frame'], row['source_seq'], row['video_frame'],
        )

    def _blank_row(self, row):
        return (
            row['source_type'], row['id'], '', '', 0,
            row['source_frame'], row['source_seq'], row['video_frame'],
        )

    def _remove_absent_assignments(self, current_identities):
        for identity in tuple(self._assignments):
            if identity not in current_identities:
                del self._assignments[identity]

    def _write_rows(self, rows):
        if self.assignmentData is None:
            return
        self.assignmentData.clear()
        self.assignmentData.appendRow(self.OUTPUT_HEADER)
        for row in rows:
            self.assignmentData.appendRow(row)

    @staticmethod
    def _logical_value(value):
        if isinstance(value, bool):
            return value
        number = GraphicSelectorExt._finite_number(value)
        if number is not None:
            return number != 0.0
        if isinstance(value, str):
            return value.strip().lower() not in ('', '0', 'false', 'off', 'no')
        return False

    @staticmethod
    def _finite_number(value):
        if value in (None, '') or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
