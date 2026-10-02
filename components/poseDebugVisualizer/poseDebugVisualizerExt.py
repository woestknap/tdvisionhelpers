"""TouchDesigner extension for the multi-person pose debug visualizer."""

import math


class PoseDebugVisualizerExt:
    """Prepare current pose rows for TouchDesigner-native rendering."""

    POSES_INPUT_HEADER = (
        'source_type', 'id', 'confidence', 'x1', 'y1', 'x2', 'y2',
        'source_frame', 'source_seq', 'video_frame',
    )
    KEYPOINTS_INPUT_HEADER = (
        'source_type', 'id', 'keypoint_id', 'keypoint_name', 'x', 'y',
        'confidence', 'source_frame', 'source_seq', 'video_frame',
    )
    POSE_DATA_HEADER = (
        'source_type', 'id', 'confidence', 'x1', 'y1', 'x2', 'y2', 'label',
    )
    KEYPOINT_DATA_HEADER = (
        'source_type', 'id', 'keypoint_id', 'keypoint_name', 'x', 'y',
        'confidence', 'visible',
    )
    SKELETON_DATA_HEADER = (
        'source_type', 'id', 'bone_index', 'start_keypoint_id',
        'end_keypoint_id', 'x1', 'y1', 'x2', 'y2', 'visible',
    )
    POSE_LABEL_REPLICAS_HEADER = ('name',)
    COCO_17_KEYPOINT_NAMES = (
        'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
        'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
        'left_wrist', 'right_wrist', 'left_hip', 'right_hip', 'left_knee',
        'right_knee', 'left_ankle', 'right_ankle',
    )
    SKELETON_CONNECTIONS = (
        (0, 1), (0, 2), (1, 3), (2, 4),
        (5, 6),
        (5, 7), (7, 9),
        (6, 8), (8, 10),
        (5, 11), (6, 12),
        (11, 12),
        (11, 13), (13, 15),
        (12, 14), (14, 16),
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.poseDataPrepared = ownerComp.op('poseDataPrepared')
        self.keypointData = ownerComp.op('keypointData')
        self.skeletonData = ownerComp.op('skeletonData')
        self.poseLabelReplicas = ownerComp.op('poseLabelReplicas')
        self._pose_label_replica_names = None

    def Update(self, force=False):
        """Reflect the current valid pose inputs without retaining state."""
        min_confidence = self._min_confidence()
        poses = self._read_poses(self._configured_op('Posesdat'))
        keypoints = self._read_keypoints(
            self._configured_op('Keypointsdat'), min_confidence)
        self._write_pose_rows(poses)
        self._sync_pose_label_replicas(len(poses))
        self._write_keypoint_rows(keypoints)
        self._write_skeleton_rows(poses, keypoints)

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    def _min_confidence(self):
        parameter = getattr(self.ownerComp.par, 'Minconfidence', None)
        if parameter is None:
            return 0.0
        try:
            value = self._finite_number(parameter.eval())
        except Exception:
            value = None
        return 0.0 if value is None else value

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

    def _read_keypoints(self, dat, min_confidence):
        rows = self._read_rows(dat, self.KEYPOINTS_INPUT_HEADER)
        if rows is None:
            return ()

        valid_rows = []
        for row in rows:
            if row['source_type'] != 'pose' or row['id'] in (None, ''):
                continue
            keypoint_id = self._keypoint_id(row['keypoint_id'])
            values = self._finite_values(row['x'], row['y'], row['confidence'])
            if keypoint_id is None or values is None:
                continue
            row['_keypoint_id'] = keypoint_id
            row['_visible'] = int(values[2] >= min_confidence)
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

    def _write_pose_rows(self, poses):
        if self.poseDataPrepared is None:
            return
        self.poseDataPrepared.clear()
        self.poseDataPrepared.appendRow(self.POSE_DATA_HEADER)
        for row in poses:
            self.poseDataPrepared.appendRow((
                row['source_type'], row['id'], row['confidence'],
                row['x1'], row['y1'], row['x2'], row['y2'],
                'pose #{}\nconf {}'.format(row['id'], row['confidence']),
            ))

    def _sync_pose_label_replicas(self, pose_count):
        """Update the Replicator template DAT only when its item list changes."""
        if self.poseLabelReplicas is None:
            self.poseLabelReplicas = self.ownerComp.op('poseLabelReplicas')
        if self.poseLabelReplicas is None:
            return

        desired = tuple('item{}'.format(index) for index in range(1, pose_count + 1))
        if self._pose_label_replica_names is None:
            self._pose_label_replica_names = self._current_replica_names()
        if desired == self._pose_label_replica_names:
            return

        self.poseLabelReplicas.clear()
        self.poseLabelReplicas.appendRow(self.POSE_LABEL_REPLICAS_HEADER)
        for name in desired:
            self.poseLabelReplicas.appendRow((name,))
        self._pose_label_replica_names = desired

    def _current_replica_names(self):
        """Return a valid current template list, or None when it needs repair."""
        try:
            if self.poseLabelReplicas.numRows < 1:
                return None
            headers = [cell.val for cell in self.poseLabelReplicas.row(0)]
            if headers != ['name']:
                return None
            names = []
            for row_index in range(1, self.poseLabelReplicas.numRows):
                row = self.poseLabelReplicas.row(row_index)
                if len(row) != 1 or row[0].val in (None, ''):
                    return None
                names.append(row[0].val)
            return tuple(names)
        except Exception:
            return None

    def _write_keypoint_rows(self, keypoints):
        if self.keypointData is None:
            return
        self.keypointData.clear()
        self.keypointData.appendRow(self.KEYPOINT_DATA_HEADER)
        for row in keypoints:
            keypoint_id = row['_keypoint_id']
            self.keypointData.appendRow((
                row['source_type'], row['id'], keypoint_id,
                self.COCO_17_KEYPOINT_NAMES[keypoint_id],
                row['x'], row['y'], row['confidence'], row['_visible'],
            ))

    def _write_skeleton_rows(self, poses, keypoints):
        if self.skeletonData is None:
            return
        self.skeletonData.clear()
        self.skeletonData.appendRow(self.SKELETON_DATA_HEADER)
        keypoints_by_identity = self._first_keypoints_by_identity(keypoints)
        for pose in poses:
            identity = (pose['source_type'], pose['id'])
            endpoints = keypoints_by_identity.get(identity, {})
            for bone_index, (start_id, end_id) in enumerate(self.SKELETON_CONNECTIONS):
                start = endpoints.get(start_id)
                end = endpoints.get(end_id)
                visible = int(
                    start is not None and end is not None
                    and start['_visible'] and end['_visible'])
                self.skeletonData.appendRow((
                    pose['source_type'], pose['id'], bone_index, start_id, end_id,
                    start['x'] if start is not None else '',
                    start['y'] if start is not None else '',
                    end['x'] if end is not None else '',
                    end['y'] if end is not None else '',
                    visible,
                ))

    @staticmethod
    def _first_keypoints_by_identity(keypoints):
        """Return the first valid keypoint for each identity/index pair."""
        grouped = {}
        for keypoint in keypoints:
            identity = (keypoint['source_type'], keypoint['id'])
            by_index = grouped.setdefault(identity, {})
            by_index.setdefault(keypoint['_keypoint_id'], keypoint)
        return grouped

    @staticmethod
    def _keypoint_id(value):
        if isinstance(value, bool):
            return None
        try:
            keypoint_id = int(value)
        except (TypeError, ValueError):
            return None
        if str(keypoint_id) != str(value).strip():
            return None
        return keypoint_id if 0 <= keypoint_id < 17 else None

    @staticmethod
    def _finite_values(*values):
        numeric_values = tuple(
            PoseDebugVisualizerExt._finite_number(value) for value in values)
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
