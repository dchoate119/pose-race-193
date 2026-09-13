"""Gesture signals -> motor commands. Pure logic, no camera/hardware deps."""

MAX_SPEED = 100

# Pivot rotates in place rather than driving forward, so it gets its own
# (lower) speed cap - full pivot at a wide-open hand would otherwise spin the
# car uncomfortably fast.
MAX_PIVOT_SPEED = 50

# Turn magnitude added/subtracted from throttle per wheel, keyed by zone label.
# Pivot zones don't use this - they rotate in place instead (see mix()).
TURN_VALUES = {
	'pivot_left': -40,
	'bend_left': -25,
	'straight': 0,
	'bend_right': 25,
	'pivot_right': 40,
}

# Forward throttle is cut to this fraction while bending, so the larger turn
# value above actually arcs the car instead of being swamped by near-max
# forward speed on both wheels.
BEND_THROTTLE_SCALE = 0.7

BEND_LABELS = frozenset(('bend_left', 'bend_right'))

# Wheel sign for in-place rotation: left wheel forward + right wheel backward
# spins the car to the right, and vice versa.
PIVOT_SIGNS = {
	'pivot_left': -1,
	'pivot_right': 1,
}

# Consecutive frames a zone must hold before it's accepted as the new state.
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


def mix(openness, zone_label):
	"""Combine hand openness + control zone into (speed_left, speed_right).

	`openness` (0.0-1.0) sets throttle magnitude - closed fist is 0 speed,
	so an unrecognized zone label fails safe to stopped. 'backward' drives
	straight reverse at that speed. 'pivot_left'/'pivot_right' rotate in
	place, scaled by openness against MAX_PIVOT_SPEED (not MAX_SPEED) -
	ignoring throttle entirely, no forward/backward motion, just a slower
	rotation. 'bend_left'/'bend_right' drive forward at a reduced throttle
	(BEND_THROTTLE_SCALE) so their turn value actually arcs the car. Every
	other zone label drives forward at full throttle, steered by
	TURN_VALUES, itself scaled by openness so a closed fist stops fully
	instead of spinning in place in a bend zone.
	"""
	throttle = MAX_SPEED * openness

	if zone_label == 'backward':
		speed = max(-100, min(100, -throttle))
		return speed, speed

	if zone_label in PIVOT_SIGNS:
		speed = PIVOT_SIGNS[zone_label] * MAX_PIVOT_SPEED * openness
		return speed, -speed

	if zone_label in BEND_LABELS:
		throttle *= BEND_THROTTLE_SCALE

	turn = TURN_VALUES.get(zone_label, 0) * openness
	speed_left = max(-100, min(100, throttle + turn))
	speed_right = max(-100, min(100, throttle - turn))
	return speed_left, speed_right
