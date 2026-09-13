# Entry point: webcam -> MediaPipe hand tracking -> gesture control -> Double Motor.
#
# Single hand controls everything: horizontal position steers (farther from
# center = stronger turn), the bottom box reverses, and how open the hand is
# sets speed (fist = 0%, fully open = 100%). See README.md
# "Pose-Controlled Maze Race" section for the full design.

import os
import time
import urllib.request

import cv2
import legoeducation as le
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from src.control import Debouncer, TURN_VALUES, mix
from src.gestures import BACKWARD_Y, BEND_OFFSET, PIVOT_OFFSET, classify_zone, hand_openness

# --- MediaPipe hand landmark model setup ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'hand_landmarker.task')
MODEL_URL = (
	'https://storage.googleapis.com/mediapipe-models/hand_landmarker/'
	'hand_landmarker/float16/latest/hand_landmarker.task'
)

if not os.path.exists(MODEL_PATH):
	os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
	print('Downloading hand_landmarker model...')
	urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

HAND_CONNECTIONS = vision.HandLandmarksConnections.HAND_CONNECTIONS

# update these values to match the Connection Card
card_color = le.LEGO_COLOR_PURPLE
card_serial = '1227'

# Connect to the Double Motor
doublemotor = le.DoubleMotor()
doublemotor.connect(card_color=card_color, card_serial=card_serial)

if not doublemotor.connected:
	print('Error connecting to Double Motor.')
	exit(1)  # error connecting

options = vision.HandLandmarkerOptions(
	base_options=BaseOptions(model_asset_path=MODEL_PATH),
	running_mode=vision.RunningMode.VIDEO,
	num_hands=1,
)

MAX_TURN = max(abs(v) for v in TURN_VALUES.values())
ARROW_LENGTH = 150


def draw_control_zones(frame):
	"""Draw the steering zones (top) and the backward box (bottom) so the driver can see them live."""
	h, w = frame.shape[:2]
	backward_y = int(BACKWARD_Y * h)

	zones = [
		(0.0, 0.5 - PIVOT_OFFSET, 'PIVOT L', (0, 0, 255)),
		(0.5 - PIVOT_OFFSET, 0.5 - BEND_OFFSET, 'BEND L', (0, 165, 255)),
		(0.5 - BEND_OFFSET, 0.5 + BEND_OFFSET, 'STRAIGHT', (0, 255, 0)),
		(0.5 + BEND_OFFSET, 0.5 + PIVOT_OFFSET, 'BEND R', (0, 165, 255)),
		(0.5 + PIVOT_OFFSET, 1.0, 'PIVOT R', (0, 0, 255)),
	]
	for start, end, label, color in zones:
		x1, x2 = int(start * w), int(end * w)
		cv2.rectangle(frame, (x1, 0), (x2, backward_y), color, 2)
		cv2.putText(frame, label, (x1 + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

	# The trigger is the wrist landmark, which dips into this zone well
	# before the visible bulk of the hand does - in practice backward
	# engages across roughly double this line's height, so the drawn box
	# is doubled to match what actually happens on screen.
	visual_top = max(0, backward_y - (h - backward_y))
	cv2.rectangle(frame, (0, visual_top), (w, h), (255, 0, 0), 8)
	cv2.putText(frame, 'BACKWARD', (10, visual_top + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)


def draw_direction_arrow(frame, zone_label, openness):
	"""Draw an arrow from frame center showing commanded direction/strength."""
	h, w = frame.shape[:2]
	origin = (w // 2, h // 2)

	if zone_label == 'backward':
		dx, dy = 0, ARROW_LENGTH * openness
	elif zone_label == 'pivot_left':
		dx, dy = -ARROW_LENGTH * openness, 0  # rotates in place, no forward motion
	elif zone_label == 'pivot_right':
		dx, dy = ARROW_LENGTH * openness, 0
	else:
		turn_frac = TURN_VALUES.get(zone_label, 0) / MAX_TURN
		dx = ARROW_LENGTH * openness * turn_frac
		dy = -ARROW_LENGTH * openness  # up = forward = negative y in image coords

	tip = (int(origin[0] + dx), int(origin[1] + dy))
	cv2.arrowedLine(frame, origin, tip, (255, 0, 255), 4, tipLength=0.3)


cap = cv2.VideoCapture(0)
zone_debouncer = Debouncer()

try:
	with vision.HandLandmarker.create_from_options(options) as landmarker:
		print("One hand: position steers, bottom box reverses, hand-openness sets speed. Press 'q' to quit.")
		while cap.isOpened():
			ok, frame = cap.read()
			if not ok:
				break

			frame = cv2.flip(frame, 1)  # mirror for a natural view
			rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
			timestamp_ms = int(time.time() * 1000)
			result = landmarker.detect_for_video(mp_image, timestamp_ms)

			openness = 0.0
			zone_raw = None
			if result.hand_landmarks:
				landmarks = result.hand_landmarks[0]
				vision.drawing_utils.draw_landmarks(frame, landmarks, HAND_CONNECTIONS)
				openness = hand_openness(landmarks)
				zone_raw = classify_zone(landmarks)

			zone_label = zone_debouncer.update(zone_raw)
			speed_left, speed_right = mix(openness, zone_label)
			doublemotor.movement_move_tank(speed_left, speed_right, blocking=False)

			draw_control_zones(frame)
			draw_direction_arrow(frame, zone_label, openness)
			status = f'zone={zone_label} openness={openness:.0%}  L={speed_left:.0f} R={speed_right:.0f}'
			cv2.putText(frame, status, (10, frame.shape[0] - 15),
						cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
			cv2.imshow('Pose Race Control', frame)

			if cv2.waitKey(1) & 0xFF == ord('q'):
				break
finally:
	doublemotor.movement_stop()
	cap.release()
	cv2.destroyAllWindows()
	doublemotor.disconnect()

exit(0)  # successful execution
