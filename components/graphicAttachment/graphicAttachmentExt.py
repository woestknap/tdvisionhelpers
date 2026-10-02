"""TouchDesigner extension for canonical graphic attachment preparation."""

import math


class GraphicAttachmentExt:
    """Apply display controls and resolve per-identity graphic sources."""

    TRANSFORM_INPUT_HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'confidence', 'visible', 'source_frame', 'source_seq', 'video_frame',
    )
    ASSIGNMENT_INPUT_HEADER = (
        'source_type', 'id', 'graphic_index', 'graphic_name', 'visible',
        'source_frame', 'source_seq', 'video_frame',
    )
    SOURCES_INPUT_HEADER = ('name', 'top')
    OUTPUT_HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'opacity', 'visible', 'graphic_index', 'graphic_name', 'graphic_top',
        'source_frame', 'source_seq', 'video_frame',
    )
    REPLICAS_HEADER = ('name',)
    REPLICA_MAP_HEADER = ('replica_index', 'transform_row')

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.graphicTransformData = ownerComp.op('graphicTransformData')
        self.graphicReplicas = ownerComp.op('graphicReplicas')
        self.graphicReplicaMap = ownerComp.op('graphicReplicaMap')
        self._replica_names = None

    def Update(self, force=False):
        """Prepare current transform rows and native-replication support data."""
        transforms = self._read_transforms(self._configured_op('Transformdat'))
        controls = self._controls()
        multisource = self._multisource()
        assignments = (
            self._read_assignments(self._configured_op('Assignmentsdat'))
            if multisource else {}
        )
        sources = (
            self._read_sources(self._configured_op('Sourcesdat'))
            if multisource else {}
        )
        fallback_top = self._graphic_top_path() if not multisource else ''
        output_rows = [
            self._output_row(transform, controls, multisource, assignments, sources, fallback_top)
            for transform in transforms
        ]
        self._write_rows(output_rows)
        self._sync_graphic_replicas(sum(1 for row in output_rows if row[8] == 1))
        self._write_replica_map(output_rows)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _controls(self):
        return (
            self._parameter_number('Scalemultiplier', 1.0),
            self._parameter_number('Rotationoffset', 0.0),
            self._parameter_number('Xoffset', 0.0),
            self._parameter_number('Yoffset', 0.0),
            self._opacity(),
            self._show_graphic(),
        )

    def _parameter_number(self, parameter_name, default):
        value = self._finite_number(self._configured_op(parameter_name))
        return default if value is None else value

    def _opacity(self):
        return max(0.0, min(1.0, self._parameter_number('Opacity', 1.0)))

    def _show_graphic(self):
        return self._logical_value(self._configured_op('Showgraphic'), True)

    def _multisource(self):
        return self._logical_value(self._configured_op('Multisource'), True)

    def _graphic_top_path(self):
        top = self._configured_op('Graphictop')
        try:
            return top.path if top is not None else ''
        except Exception:
            return ''

    @staticmethod
    def _read_rows(dat, required_columns):
        if dat is None:
            return None
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {column: headers.index(column) for column in required_columns}
            return [
                {column: dat[row_index, column_index].val for column, column_index in indices.items()}
                for row_index in range(1, dat.numRows)
            ]
        except Exception:
            return None

    def _read_transforms(self, dat):
        rows = self._read_rows(dat, self.TRANSFORM_INPUT_HEADER)
        if rows is None:
            return ()
        return tuple(
            row for row in rows
            if row['source_type'] not in (None, '') and row['id'] not in (None, '')
            and row['anchor'] not in (None, '')
        )

    def _read_assignments(self, dat):
        rows = self._read_rows(dat, self.ASSIGNMENT_INPUT_HEADER)
        if rows is None:
            return {}
        assignments = {}
        for row in rows:
            identity = (row['source_type'], row['id'])
            index = self._physical_index(row['graphic_index'])
            if identity[0] in (None, '') or identity[1] in (None, '') or index is None:
                continue
            # The first valid row owns a duplicate canonical identity.
            if identity not in assignments:
                assignments[identity] = (index, self._logical_value(row['visible']))
        return assignments

    def _read_sources(self, dat):
        rows = self._read_rows(dat, self.SOURCES_INPUT_HEADER)
        if rows is None:
            return {}
        sources = {}
        for physical_index, row in enumerate(rows):
            if row['name'] in (None, ''):
                continue
            sources[physical_index] = {'name': row['name'], 'top': row['top'] or ''}
        return sources

    def _write_rows(self, rows):
        table = self._table('graphicTransformData')
        if table is None:
            return
        table.clear()
        table.appendRow(self.OUTPUT_HEADER)
        for row in rows:
            table.appendRow(row)

    def _output_row(self, transform, controls, multisource, assignments, sources, fallback_top):
        scale_multiplier, rotation_offset, x_offset, y_offset, opacity, show = controls
        input_x = self._finite_number(transform['x'])
        input_y = self._finite_number(transform['y'])
        input_scale = self._finite_number(transform['scale'])
        input_rotation = self._finite_number(transform['rotation'])
        input_confidence = self._finite_number(transform['confidence'])
        x = '' if input_x is None else input_x + x_offset
        y = '' if input_y is None else input_y + y_offset
        scale = '' if input_scale is None else input_scale * scale_multiplier
        rotation = '' if input_rotation is None else input_rotation + rotation_offset
        transform_valid = all(value is not None for value in (
            input_x, input_y, input_scale, input_rotation, input_confidence,
        ))
        graphic_index = graphic_name = graphic_top = ''
        source_visible = True
        if multisource:
            assignment = assignments.get((transform['source_type'], transform['id']))
            if assignment is None:
                source_visible = False
            else:
                assigned_index, assignment_visible = assignment
                source = sources.get(assigned_index)
                if source is None:
                    source_visible = False
                else:
                    graphic_index = assigned_index
                    graphic_name = source['name']
                    graphic_top = source['top']
                    source_visible = assignment_visible and bool(graphic_top)
        else:
            graphic_top = fallback_top
        visible = int(
            self._logical_value(transform['visible']) and show and transform_valid and source_visible
        )
        return (
            transform['source_type'], transform['id'], transform['anchor'],
            x, y, scale, rotation, opacity, visible,
            graphic_index, graphic_name, graphic_top,
            transform['source_frame'], transform['source_seq'], transform['video_frame'],
        )

    def _sync_graphic_replicas(self, visible_count):
        desired = tuple('item{}'.format(index) for index in range(1, visible_count + 1))
        table = self._table('graphicReplicas')
        if table is None:
            return
        if self._replica_names is None:
            self._replica_names = self._current_replica_names(table)
        if desired == self._replica_names:
            return
        table.clear()
        table.appendRow(self.REPLICAS_HEADER)
        for name in desired:
            table.appendRow((name,))
        self._replica_names = desired

    def _write_replica_map(self, output_rows):
        table = self._table('graphicReplicaMap')
        if table is None:
            return
        table.clear()
        table.appendRow(self.REPLICA_MAP_HEADER)
        replica_index = 0
        for transform_row, row in enumerate(output_rows):
            if row[8] == 1:
                table.appendRow((replica_index, transform_row))
                replica_index += 1

    def _table(self, attribute_name):
        table = getattr(self, attribute_name)
        if table is None:
            table = self.ownerComp.op(attribute_name)
            setattr(self, attribute_name, table)
        return table

    @staticmethod
    def _current_replica_names(table):
        try:
            if [cell.val for cell in table.row(0)] != ['name']:
                return None
            return tuple(table[row_index, 0].val for row_index in range(1, table.numRows))
        except Exception:
            return None

    @staticmethod
    def _physical_index(value):
        number = GraphicAttachmentExt._finite_number(value)
        if number is None or number < 0.0 or number != int(number):
            return None
        return int(number)

    @staticmethod
    def _logical_value(value, default=False):
        if isinstance(value, bool):
            return value
        number = GraphicAttachmentExt._finite_number(value)
        if number is not None:
            return number != 0.0
        if isinstance(value, str):
            return value.strip().lower() not in ('', '0', 'false', 'off', 'no')
        return default

    @staticmethod
    def _finite_number(value):
        if value in (None, '') or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
