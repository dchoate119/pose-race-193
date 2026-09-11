# MediaPipe Hand Tracking -> Double Motor Test
#
# Basic smoke test: track one hand with MediaPipe, and start the Double
# Motor whenever the hand is raised above shoulder height in the frame.
#
# Note: mediapipe 1.0.1 dropped the old `mp.solutions` API in favor of the
# Tasks API used below, so this only works with mediapipe>=0.10.30-ish.

import os
import time
import urllib.request

import cv2
import legoeducation as le
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

# --- MediaPipe hand landmark model setup ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'hand_landmarker.task')
MODEL_URL = (
	'https://storage.googleapis.com/mediapipe-models/hand_landmarker/'
	'hand_landmarker/float16/latest/hand_landmarker.task'
)

if not os.path.exists(MODEL_PATH):
	print('Downloading hand_landmarker model...')
	urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

# Wrist landmark index in the 21-point hand model
WRIST = 0

# Normalized y-threshold (0 = top of frame, 1 = bottom): hand above this
# counts as "raised"
RAISE_THRESHOLD = 0.5

# Hand segment connections (Connection objects with .start/.end attributes,
# which is what draw_landmarks expects)
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

cap = cv2.VideoCapture(0)
hand_raised = False

try:
	with vision.HandLandmarker.create_from_options(options) as landmarker:
		print("Raise your hand to start the Double Motor. Press 'q' to quit.")
		while cap.isOpened():
			ok, frame = cap.read()
			if not ok:
				break

			frame = cv2.flip(frame, 1)  # mirror for a natural view
			rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
			timestamp_ms = int(time.time() * 1000)
			result = landmarker.detect_for_video(mp_image, timestamp_ms)

			currently_raised = False
			if result.hand_landmarks:
				landmarks = result.hand_landmarks[0]
				vision.drawing_utils.draw_landmarks(frame, landmarks, HAND_CONNECTIONS)
				currently_raised = landmarks[WRIST].y < RAISE_THRESHOLD

			# edge-triggered: only act when the state changes
			if currently_raised and not hand_raised:
				print('> Hand raised - starting Double Motor')
				doublemotor.movement_move(direction=le.MOVEMENT_DIRECTION_FORWARD, speed=30, blocking=False)
			elif not currently_raised and hand_raised:
				print('> Hand lowered - stopping Double Motor')
				doublemotor.movement_stop(blocking=False)

			hand_raised = currently_raised

			status = 'RAISED' if hand_raised else 'lowered'
			cv2.putText(frame, f'Hand: {status}', (10, 30),
						cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
			cv2.imshow('MediaPipe Hand Test', frame)

			if cv2.waitKey(1) & 0xFF == ord('q'):
				break
finally:
	doublemotor.movement_stop()
	cap.release()
	cv2.destroyAllWindows()
	doublemotor.disconnect()

exit(0)  # successful execution
