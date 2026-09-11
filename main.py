# Entry point: webcam -> MediaPipe hand tracking -> gesture control -> Double Motor.
#
# Left hand = throttle (shape-based), right hand = turning (position-based).
# See README.md "Pose-Controlled Maze Race" section for the full design.

import os
import time
import urllib.request

import cv2
import legoeducation as le
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from src.control import Debouncer, mix
from src.gestures import BEND_OFFSET, PIVOT_OFFSET, classify_throttle_hand, classify_turn_hand

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
	num_hands=2,
)


def split_hands(result):
	"""Return (left_landmarks, right_landmarks); either may be None.

	Handedness assumes a mirrored/selfie-style input, which is why the frame
	is flipped before detection below.
	"""
	left = right = None
	for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
		label = handedness[0].category_name
		if label == 'Left':
			left = landmarks
		elif label == 'Right':
			right = landmarks
	return left, right


def draw_turn_zones(frame):
	"""Draw boxes over the turn thresholds so the driver can see them live."""
	h, w = frame.shape[:2]
	zones = [
		(0.0, 0.5 - PIVOT_OFFSET, 'PIVOT L', (0, 0, 255)),
		(0.5 - PIVOT_OFFSET, 0.5 - BEND_OFFSET, 'BEND L', (0, 165, 255)),
		(0.5 - BEND_OFFSET, 0.5 + BEND_OFFSET, 'STRAIGHT', (0, 255, 0)),
		(0.5 + BEND_OFFSET, 0.5 + PIVOT_OFFSET, 'BEND R', (0, 165, 255)),
		(0.5 + PIVOT_OFFSET, 1.0, 'PIVOT R', (0, 0, 255)),
	]
	for start, end, label, color in zones:
		x1, x2 = int(start * w), int(end * w)
		cv2.rectangle(frame, (x1, 0), (x2, h), color, 2)
		cv2.putText(frame, label, (x1 + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


cap = cv2.VideoCapture(0)
throttle_debouncer = Debouncer()
turn_debouncer = Debouncer()

try:
	with vision.HandLandmarker.create_from_options(options) as landmarker:
		print("Left hand = throttle, right hand = turn. Press 'q' to quit.")
		while cap.isOpened():
			ok, frame = cap.read()
			if not ok:
				break

			frame = cv2.flip(frame, 1)  # mirror view; matches handedness convention
			rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
			timestamp_ms = int(time.time() * 1000)
			result = landmarker.detect_for_video(mp_image, timestamp_ms)

			for landmarks in result.hand_landmarks:
				vision.drawing_utils.draw_landmarks(frame, landmarks, HAND_CONNECTIONS)

			left_landmarks, right_landmarks = split_hands(result)
			throttle_raw = classify_throttle_hand(left_landmarks) if left_landmarks else None
			turn_raw = classify_turn_hand(right_landmarks) if right_landmarks else None

			throttle_label = throttle_debouncer.update(throttle_raw)
			turn_label = turn_debouncer.update(turn_raw)

			speed_left, speed_right = mix(throttle_label, turn_label)
			doublemotor.movement_move_tank(speed_left, speed_right, blocking=False)

			draw_turn_zones(frame)
			status = f'throttle={throttle_label} turn={turn_label}  L={speed_left} R={speed_right}'
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
