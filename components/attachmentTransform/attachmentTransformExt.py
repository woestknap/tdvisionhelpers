"""TouchDesigner extension for canonical pose attachment transforms."""

import math


class AttachmentTransformExt:
    """Prepare one 2D attachment transform for every current valid pose."""

    POSES_INPUT_HEADER = (
        'source_type', 'id', 'confidence', 'x1', 'y1', 'x2', 'y2',
        'source_frame', 'source_seq', 'video_frame',
    )
    KEYPOINTS_INPUT_HEADER = (
        'source_type', 'id', 'keypoint_id', 'keypoint_name', 'x', 'y',
        'confidence', 'source_frame', 'source_seq', 'video_frame',
    )
    TRANSFORM_HEADER = (
        'source_type', 'id', 'anchor', 'x', 'y', 'scale', 'rotation',
        'confidence', 'visible', 'source_frame', 'source_seq', 'video_frame',
    )
    KEYPOINT_NAMES = (
        'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
        'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
        'left_wrist', 'right_wrist', 'left_hip', 'right_hip', 'left_knee',
        'right_knee', 'left_ankle', 'right_ankle',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.transformData = ownerComp.op('transformData')

    def Update(self, force=False):
        """Write current transforms, or a header-only table for invalid input."""
        mode = self._mode()
        point = self._keypoint_name('Point')
        point_a = self._keypoint_name('Pointa')
        point_b = self._keypoint_name('Pointb')
        min_confidence = self._min_confidence()
        poses = self._read_poses(self._configured_op('Posesdat'))
        keypoints = self._first_keypoints_by_identity_and_name(
            self._configured_op('Keypointsdat'))
        self._write_transforms(
            poses, keypoints, mode, point, point_a, point_b, min_confidence)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _parameter_text(self, parameter_name):
        value = self._configured_parameter_value(parameter_name)
        return value.strip() if isinstance(value, str) else ''

    def _configured_parameter_value(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _mode(self):
        mode = self._parameter_text('Mode').lower()
        return mode if mode in ('point', 'segment') else None

    def _keypoint_name(self, parameter_name):
        name = self._parameter_text(parameter_name)
        return name if name in self.KEYPOINT_NAMES else None

    def _min_confidence(self):
        value = self._finite_number(self._configured_parameter_value('Minconfidence'))
        return 0.25 if value is None else value

    def _read_poses(self, dat):
        rows = self._read_rows(dat, self.POSES_INPUT_HEADER)
        if rows is None:
            return ()

        valid_rows = []
        for row in rows:
            if row['source_type'] != 'pose' or row['id'] in (None, ''):
                continue
            if self._finite_values(
                row['confidence'], row['x1'], row['y1'], row['x2'], row['y2'],
            ) is None:
                continue
            valid_rows.append(row)
        return valid_rows

    @staticmethod
    def _read_rows(dat, required_columns):
        if dat is None:
            return None
        try:
            headers = [cell.val for cell in dat.row(0)]
            indices = {column: headers.index(column) for column in required_columns}
            return [
                {column: dat[row_index, column_index].val
                 for column, column_index in indices.items()}
                for row_index in range(1, dat.numRows)
            ]
        except Exception:
            return None

    def _first_keypoints_by_identity_and_name(self, dat):
        rows = self._read_rows(dat, self.KEYPOINTS_INPUT_HEADER)
        if rows is None:
            return {}

        keypoints = {}
        for row in rows:
            name = row['keypoint_name']
            identity = (row['source_type'], row['id'])
            values = self._finite_values(row['x'], row['y'], row['confidence'])
            if (
                identity[0] != 'pose' or identity[1] in (None, '')
                or name not in self.KEYPOINT_NAMES or values is None
            ):
                continue
            keypoints.setdefault((identity[0], identity[1], name), (
                row['x'], row['y'], row['confidence'], values[0], values[1], values[2],
            ))
        return keypoints

    def _write_transforms(
            self, poses, keypoints, mode, point, point_a, point_b, min_confidence):
        if self.transformData is None:
            return
        self.transformData.clear()
        self.transformData.appendRow(self.TRANSFORM_HEADER)
        for pose in poses:
            if mode == 'point':
                values = self._point_transform(pose, keypoints, point, min_confidence)
            elif mode == 'segment':
                values = self._segment_transform(
                    pose, keypoints, point_a, point_b, min_confidence)
            else:
                values = ('', '', '', '', '', '', 0)
            anchor, x, y, scale, rotation, confidence, visible = values
            self.transformData.appendRow((
                pose['source_type'], pose['id'], anchor, x, y, scale, rotation,
                confidence, visible, pose['source_frame'], pose['source_seq'],
                pose['video_frame'],
            ))

    def _point_transform(self, pose, keypoints, point, min_confidence):
        if point is None:
            return ('', '', '', '', '', '', 0)
        keypoint = keypoints.get((pose['source_type'], pose['id'], point))
        if keypoint is None:
            return (point, '', '', '', '', '', 0)
        x, y, confidence, _, _, numeric_confidence = keypoint
        return (
            point, x, y, 1.0, 0.0, confidence,
            int(numeric_confidence >= min_confidence),
        )

    def _segment_transform(self, pose, keypoints, point_a, point_b, min_confidence):
        if point_a is None or point_b is None:
            return ('', '', '', '', '', '', 0)
        anchor = '{}_{}'.format(point_a, point_b)
        keypoint_a = keypoints.get((pose['source_type'], pose['id'], point_a))
        keypoint_b = keypoints.get((pose['source_type'], pose['id'], point_b))
        if keypoint_a is None or keypoint_b is None:
            return (anchor, '', '', '', '', '', 0)

        _, _, _, ax, ay, confidence_a = keypoint_a
        _, _, _, bx, by, confidence_b = keypoint_b
        dx = bx - ax
        dy = by - ay
        confidence = min(confidence_a, confidence_b)
        return (
            anchor, (ax + bx) * 0.5, (ay + by) * 0.5,
            math.sqrt(dx * dx + dy * dy), math.degrees(math.atan2(dy, dx)),
            confidence, int(confidence_a >= min_confidence and confidence_b >= min_confidence),
        )

    @staticmethod
    def _finite_values(*values):
        numeric_values = tuple(
            AttachmentTransformExt._finite_number(value) for value in values)
        return None if any(value is None for value in numeric_values) else numeric_values

    @staticmethod
    def _finite_number(value):
        if value in (None, '') or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
