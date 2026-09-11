"""Hand landmarks -> gesture labels. Pure functions, no camera/hardware deps."""

# Standard MediaPipe hand landmark indices (21 points/hand)
WRIST = 0
THUMB_MCP = 2
THUMB_TIP = 4
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

# Normalized horizontal offset from frame center (x=0.5) that separates
# straight / bend / pivot turn zones.
BEND_OFFSET = 0.08
PIVOT_OFFSET = 0.20


def _dist(a, b):
	return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _is_extended(landmarks, mcp_idx, tip_idx):
	wrist = landmarks[WRIST]
	return _dist(landmarks[tip_idx], wrist) > _dist(landmarks[mcp_idx], wrist) * EXTENDED_RATIO


def classify_throttle_hand(landmarks):
	"""Classify a hand's shape into a throttle gesture.

	Returns 'forward', 'stop', 'backward', or None if the shape is
	ambiguous/transitional.
	"""
	fingers_extended = [_is_extended(landmarks, mcp, tip) for mcp, tip in FINGER_JOINTS]
	thumb_extended = _is_extended(landmarks, THUMB_MCP, THUMB_TIP)

	if all(fingers_extended):
		return 'forward'
	if not any(fingers_extended):
		return 'backward' if thumb_extended else 'stop'
	return None


def classify_turn_hand(landmarks):
	"""Classify a hand's horizontal position into a turn gesture.

	Returns 'pivot_left', 'bend_left', 'straight', 'bend_right', or
	'pivot_right', based on the wrist's offset from the frame's horizontal
	center. A closed fist always forces 'straight', regardless of position -
	a safety override to explicitly turn off turning.
	"""
	fingers_extended = [_is_extended(landmarks, mcp, tip) for mcp, tip in FINGER_JOINTS]
	if not any(fingers_extended):
		return 'straight'

	offset = landmarks[WRIST].x - 0.5  # negative = left of center

	if abs(offset) < BEND_OFFSET:
		return 'straight'
	if offset < 0:
		return 'pivot_left' if offset <= -PIVOT_OFFSET else 'bend_left'
	return 'pivot_right' if offset >= PIVOT_OFFSET else 'bend_right'
