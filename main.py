# Entry point: webcam -> MediaPipe hand tracking -> gesture control -> Double Motor.
#
# Single hand controls both throttle (shape) and turning (horizontal
# position): open hand = forward, fist = backward. Seeing both hands at once
# is a safety stop override. See README.md "Pose-Controlled Maze Race" for
# the full design.

import os
import time
import urllib.request

import cv2
import legoeducation as le
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from src.control import Debouncer, mix
from src.gestures import WRIST, classify_hand_shape, turn_from_offset

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


def draw_turn_indicator(frame, hand_x=None):
	"""Draw a center reference line, plus the hand's live offset if visible."""
	h, w = frame.shape[:2]
	cx = w // 2
	cv2.line(frame, (cx, 0), (cx, h), (200, 200, 200), 1)
	if hand_x is not None:
		hx = int(hand_x * w)
		cv2.line(frame, (cx, h // 2), (hx, h // 2), (0, 255, 255), 3)


cap = cv2.VideoCapture(0)
throttle_debouncer = Debouncer()

try:
	with vision.HandLandmarker.create_from_options(options) as landmarker:
		print("One hand: open = forward, fist = backward, position = turn.")
		print("Both hands visible = stop. Press 'q' to quit.")
		while cap.isOpened():
			ok, frame = cap.read()
			if not ok:
				break

			frame = cv2.flip(frame, 1)  # mirror view, so on-screen left/right match turning
			rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
			timestamp_ms = int(time.time() * 1000)
			result = landmarker.detect_for_video(mp_image, timestamp_ms)

			for landmarks in result.hand_landmarks:
				vision.drawing_utils.draw_landmarks(frame, landmarks, HAND_CONNECTIONS)

			if len(result.hand_landmarks) == 1:
				landmarks = result.hand_landmarks[0]
				throttle_raw = classify_hand_shape(landmarks)
				turn_value = turn_from_offset(landmarks)
				hand_x = landmarks[WRIST].x
			else:
				# Zero hands (fail-safe) or both hands (safety stop override).
				throttle_raw = None
				turn_value = 0.0
				hand_x = None

			throttle_label = throttle_debouncer.update(throttle_raw)

			speed_left, speed_right = mix(throttle_label, turn_value)
			doublemotor.movement_move_tank(speed_left, speed_right, blocking=False)

			draw_turn_indicator(frame, hand_x)
			status = f'throttle={throttle_label} turn={turn_value:.0f}  L={speed_left} R={speed_right}'
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
