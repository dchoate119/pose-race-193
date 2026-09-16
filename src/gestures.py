"""Hand landmarks -> control signals. Pure functions, no camera/hardware deps."""

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

# Finger tip/wrist distance normalized by knuckle/wrist distance, at a closed
# fist vs. a fully open hand. Openness is a linear map between the two -
# tune these against your own camera/hand if 0%/100% don't feel right.
CLOSED_RATIO = 1.0
OPEN_RATIO = 1.8

# Normalized horizontal offset from frame center (x=0.5) that separates
# straight / bend / pivot turn zones.
BEND_OFFSET = 0.08
PIVOT_OFFSET = 0.20

# Normalized vertical position (0=top, 1=bottom) below which the hand is in
# the "backward" box, regardless of horizontal position. This triggers off
# the wrist landmark specifically, which sits at the base of the hand and so
# dips below this line before the visible bulk of the hand does - keep this
# close to 1.0 so the backward area stays small and near the bottom edge.
BACKWARD_Y = 0.85


def _dist(a, b):
	return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def hand_openness(landmarks):
	"""Continuous throttle: 0.0 (closed fist) - 1.0 (fully open hand).

	Averages, over the four fingers, how far each fingertip sits from the
	wrist relative to its own knuckle - curled fingers sit close, extended
	fingers sit far.
	"""
	wrist = landmarks[WRIST]
	ratios = [_dist(landmarks[tip], wrist) / _dist(landmarks[mcp], wrist) for mcp, tip in FINGER_JOINTS]
	avg_ratio = sum(ratios) / len(ratios)
	openness = (avg_ratio - CLOSED_RATIO) / (OPEN_RATIO - CLOSED_RATIO)
	return max(0.0, min(1.0, openness))


def classify_zone(landmarks):
	"""Classify wrist position into a control zone.

	Returns 'backward' when the hand is low enough in frame (the reverse
	box), otherwise a turn zone based on horizontal position: 'pivot_left',
	'bend_left', 'straight', 'bend_right', or 'pivot_right'. Farther from
	center means a stronger turn.
	"""
	if landmarks[WRIST].y >= BACKWARD_Y:
		return 'backward'

	offset = landmarks[WRIST].x - 0.5  # negative = left of center
	if abs(offset) < BEND_OFFSET:
		return 'straight'
	if offset < 0:
		return 'pivot_left' if offset <= -PIVOT_OFFSET else 'bend_left'
	return 'pivot_right' if offset >= PIVOT_OFFSET else 'bend_right'
