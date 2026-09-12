"""Hand landmarks -> gesture signals. Pure functions, no camera/hardware deps."""

# Standard MediaPipe hand landmark indices (21 points/hand)
WRIST = 0
INDEX_MCP = 5
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_TIP = 12
RING_MCP = 13
RING_TIP = 16
PINKY_MCP = 17
PINKY_TIP = 20

FINGER_JOINTS = (
	(INDEX_MCP, INDEX_TIP),
	(MIDDLE_MCP, MIDDLE_TIP),
	(RING_MCP, RING_TIP),
	(PINKY_MCP, PINKY_TIP),
)

# A finger counts as extended when its tip sits at least this many times
# farther from the wrist than its own knuckle (MCP) is.
EXTENDED_RATIO = 1.3

# Turn speed maxes out once the wrist is this far (normalized, 0-0.5) from
# frame center; scaled linearly in between.
TURN_EDGE_OFFSET = 0.4
TURN_MAX = 40
TURN_GAIN = TURN_MAX / TURN_EDGE_OFFSET


def _dist(a, b):
	return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _is_extended(landmarks, mcp_idx, tip_idx):
	wrist = landmarks[WRIST]
	return _dist(landmarks[tip_idx], wrist) > _dist(landmarks[mcp_idx], wrist) * EXTENDED_RATIO


def classify_hand_shape(landmarks):
	"""Classify a hand's shape into a throttle direction.

	Returns 'forward' (open hand), 'backward' (fist), or None if the shape
	is ambiguous/transitional.
	"""
	fingers_extended = [_is_extended(landmarks, mcp, tip) for mcp, tip in FINGER_JOINTS]

	if all(fingers_extended):
		return 'forward'
	if not any(fingers_extended):
		return 'backward'
	return None


def turn_from_offset(landmarks):
	"""Continuous turn speed from the hand's horizontal offset from center.

	Offset is measured from the wrist, since it stays stable regardless of
	hand shape (open vs. fist). Positive = right, negative = left.
	"""
	offset = landmarks[WRIST].x - 0.5
	turn = offset * TURN_GAIN
	return max(-TURN_MAX, min(TURN_MAX, turn))
