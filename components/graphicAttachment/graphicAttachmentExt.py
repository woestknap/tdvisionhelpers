"""TouchDesigner extension for multi-person graphic attachment data."""

import math


class GraphicAttachmentExt:
    """Apply graphic display controls to current canonical attachment transforms."""

    TRANSFORM_INPUT_HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'confidence', 'visible', 'source_frame', 'source_seq', 'video_frame',
    )

    OUTPUT_HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'opacity', 'visible', 'source_frame', 'source_seq', 'video_frame',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.graphicTransformData = ownerComp.op('graphicTransformData')

    def Update(self, force=False):
        """Write current display transforms, or a header-only table for bad input."""
        transforms = self._read_transforms(
            self._configured_op('Transformdat')
        )

        controls = self._controls()

        self._write_rows(
            transforms,
            controls,
        )

    def _configured_op(self, parameter_name):
        parameter = getattr(
            self.ownerComp.par,
            parameter_name,
            None,
        )

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
        value = self._finite_number(
            self._configured_op_value(parameter_name)
        )

        return default if value is None else value

    def _configured_op_value(self, parameter_name):
        parameter = getattr(
            self.ownerComp.par,
            parameter_name,
            None,
        )

        if parameter is None:
            return None

        try:
            return parameter.eval()
        except Exception:
            return None

    def _opacity(self):
        return max(
            0.0,
            min(
                1.0,
                self._parameter_number('Opacity', 1.0),
            ),
        )

    def _show_graphic(self):
        value = self._configured_op_value('Showgraphic')

        # TouchDesigner Toggle parameters may evaluate directly
        # to Python bool values.
        if isinstance(value, bool):
            return value

        # Also support numeric toggle values such as 0 / 1.
        number = self._finite_number(value)

        if number is not None:
            return number != 0.0

        # Graceful fallback for string-like values.
        if isinstance(value, str):
            return value.strip().lower() not in (
                '',
                '0',
                'false',
                'off',
                'no',
            )

        # Preserve previous permissive fallback for unexpected
        # parameter return types.
        return True

    @staticmethod
    def _read_rows(dat, required_columns):
        if dat is None:
            return None

        try:
            headers = [
                cell.val
                for cell in dat.row(0)
            ]

            indices = {
                column: headers.index(column)
                for column in required_columns
            }

            return [
                {
                    column: dat[row_index, column_index].val
                    for column, column_index in indices.items()
                }
                for row_index in range(1, dat.numRows)
            ]

        except Exception:
            return None

    def _read_transforms(self, dat):
        rows = self._read_rows(
            dat,
            self.TRANSFORM_INPUT_HEADER,
        )

        if rows is None:
            return ()

        return [
            row
            for row in rows
            if row['source_type'] not in (None, '')
            and row['id'] not in (None, '')
            and row['anchor'] not in (None, '')
        ]

    def _write_rows(self, transforms, controls):
        if self.graphicTransformData is None:
            return

        self.graphicTransformData.clear()
        self.graphicTransformData.appendRow(
            self.OUTPUT_HEADER
        )

        for transform in transforms:
            self.graphicTransformData.appendRow(
                self._output_row(
                    transform,
                    controls,
                )
            )

    def _output_row(self, transform, controls):
        (
            scale_multiplier,
            rotation_offset,
            x_offset,
            y_offset,
            opacity,
            show,
        ) = controls

        input_x = self._finite_number(
            transform['x']
        )

        input_y = self._finite_number(
            transform['y']
        )

        input_scale = self._finite_number(
            transform['scale']
        )

        input_rotation = self._finite_number(
            transform['rotation']
        )

        input_confidence = self._finite_number(
            transform['confidence']
        )

        input_visible = self._finite_number(
            transform['visible']
        )

        x = (
            ''
            if input_x is None
            else input_x + x_offset
        )

        y = (
            ''
            if input_y is None
            else input_y + y_offset
        )

        scale = (
            ''
            if input_scale is None
            else input_scale * scale_multiplier
        )

        rotation = (
            ''
            if input_rotation is None
            else input_rotation + rotation_offset
        )

        required_valid = all(
            value is not None
            for value in (
                input_x,
                input_y,
                input_scale,
                input_rotation,
                input_confidence,
            )
        )

        visible = int(
            input_visible == 1.0
            and show
            and required_valid
        )

        return (
            transform['source_type'],
            transform['id'],
            transform['anchor'],
            x,
            y,
            scale,
            rotation,
            opacity,
            visible,
            transform['source_frame'],
            transform['source_seq'],
            transform['video_frame'],
        )

    @staticmethod
    def _finite_number(value):
        if value in (None, ''):
            return None

        if isinstance(value, bool):
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        return (
            number
            if math.isfinite(number)
            else None
        )