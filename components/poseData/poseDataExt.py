"""TouchDesigner extension for the Phase 6 poseData adapter."""

import json
import math


class PoseDataExt:
    """Convert current yolo-touchdesigner pose JSON into canonical pose DATs."""

    POSES_HEADER = (
        'source_type', 'id', 'confidence', 'x1', 'y1', 'x2', 'y2',
        'source_frame', 'source_seq', 'video_frame',
    )
    KEYPOINTS_HEADER = (
        'source_type', 'id', 'keypoint_id', 'keypoint_name', 'x', 'y',
        'confidence', 'source_frame', 'source_seq', 'video_frame',
    )
    COCO_17_KEYPOINT_NAMES = (
        'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
        'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
        'left_wrist', 'right_wrist', 'left_hip', 'right_hip', 'left_knee',
        'right_knee', 'left_ankle', 'right_ankle',
    )

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.poses = ownerComp.op('poses')
        self.keypoints = ownerComp.op('keypoints')

        # DAT cookCount is not reliable for the live upstream predictions DAT.
        self._source_dat = None
        self._source_text = None
        self._has_written_output = False

    def Update(self, force=False):
        """Write current pose records, or header-only tables for invalid input."""
        source_dat = self._configured_op('Source')
        source_text = self._read_source_text(source_dat)
        source_changed = (
            source_dat is not self._source_dat
            or source_text != self._source_text
        )
        if not force and self._has_written_output and not source_changed:
            return

        self._source_dat = source_dat
        self._source_text = source_text
        poses, keypoints = self._rows_from_message(self._read_message(source_text))
        self._write_rows(poses, keypoints)
        self._has_written_output = True

    def _configured_op(self, parameter_name):
        parameter = getattr(self.ownerComp.par, parameter_name, None)
        if parameter is None:
            return None
        try:
            return parameter.eval()
        except Exception:
            return None

    @staticmethod
    def _read_source_text(source_dat):
        if source_dat is None:
            return ''
        try:
            return source_dat.text
        except Exception:
            return ''

    @staticmethod
    def _read_message(source_text):
        try:
            message = json.loads(source_text)
        except Exception:
            return None
        return message if isinstance(message, dict) else None

    def _rows_from_message(self, message):
        if not isinstance(message, dict):
            return (), ()

        pose_records = message.get('yolo_pose')
        if not isinstance(pose_records, list):
            return (), ()

        source_frame = message.get('frame', '')
        source_seq = message.get('seq', '')
        video_frame = message.get('videoFrame', '')
        pose_rows = []
        keypoint_rows = []
        for pose in pose_records:
            pose_row = self._pose_row(
                pose, source_frame, source_seq, video_frame)
            if pose_row is None:
                continue
            pose_rows.append(pose_row)
            keypoint_rows.extend(self._keypoint_rows(
                pose, source_frame, source_seq, video_frame))
        return pose_rows, keypoint_rows

    def _pose_row(self, pose, source_frame, source_seq, video_frame):
        if not isinstance(pose, dict):
            return None
        pose_id = pose.get('id')
        if pose_id is None:
            return None

        values = self._finite_values(
            pose.get('tx'), pose.get('ty'), pose.get('width'),
            pose.get('height'), pose.get('score'),
        )
        if values is None:
            return None
        tx, ty, width, height, _ = values

        # yolo_pose tx/ty are already bottom-left bbox coordinates.
        return (
            'pose', pose_id, pose['score'], pose['tx'], pose['ty'],
            tx + width, ty + height,
            source_frame, source_seq, video_frame,
        )

    def _keypoint_rows(self, pose, source_frame, source_seq, video_frame):
        keypoints = pose.get('keypoints')
        if not isinstance(keypoints, list):
            return ()

        rows = []
        pose_id = pose['id']
        for keypoint_id, keypoint in enumerate(keypoints[:17]):
            if not isinstance(keypoint, dict):
                continue
            if self._finite_values(
                keypoint.get('x'), keypoint.get('y'), keypoint.get('score'),
            ) is None:
                continue
            rows.append((
                'pose', pose_id, keypoint_id,
                self.COCO_17_KEYPOINT_NAMES[keypoint_id],
                keypoint['x'], keypoint['y'], keypoint['score'],
                source_frame, source_seq, video_frame,
            ))
        return rows

    @staticmethod
    def _finite_values(*values):
        if any(isinstance(value, bool) for value in values):
            return None
        try:
            numeric_values = tuple(float(value) for value in values)
        except (TypeError, ValueError):
            return None
        return numeric_values if all(math.isfinite(value) for value in numeric_values) else None

    def _write_rows(self, pose_rows, keypoint_rows):
        if self.poses is not None:
            self.poses.clear()
            self.poses.appendRow(self.POSES_HEADER)
            for row in pose_rows:
                self.poses.appendRow(row)

        if self.keypoints is not None:
            self.keypoints.clear()
            self.keypoints.appendRow(self.KEYPOINTS_HEADER)
            for row in keypoint_rows:
                self.keypoints.appendRow(row)
