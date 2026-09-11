"""Gesture labels -> motor commands. Pure logic, no camera/hardware deps."""

# Speed percentages fed into the differential-drive mixing formula.
THROTTLE_VALUES = {
	'forward': 40,
	'stop': 0,
	'backward': -40,
}

TURN_VALUES = {
	'pivot_left': -40,
	'bend_left': -15,
	'straight': 0,
	'bend_right': 15,
	'pivot_right': 40,
}

# Consecutive frames a gesture must hold before it's accepted as the new state.
DEBOUNCE_FRAMES = 5


class Debouncer:
	"""Only accepts a new gesture label once it's held for N consecutive frames."""

	def __init__(self, frames=DEBOUNCE_FRAMES, default=None):
		self._frames = frames
		self._current = default
		self._candidate = default
		self._count = 0

	def update(self, label):
		if label == self._candidate:
			self._count += 1
		else:
			self._candidate = label
			self._count = 1

		if self._count >= self._frames:
			self._current = self._candidate

		return self._current


def mix(throttle_label, turn_label):
	"""Combine throttle + turn gesture labels into (speed_left, speed_right).

	Unrecognized labels (hand not detected, ambiguous shape, debounce not yet
	settled) default to 0, so the fail-safe behavior is to stop.
	"""
	throttle = THROTTLE_VALUES.get(throttle_label, 0)
	turn = TURN_VALUES.get(turn_label, 0)

	speed_left = max(-100, min(100, throttle + turn))
	speed_right = max(-100, min(100, throttle - turn))
	return speed_left, speed_right
