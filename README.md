# MobileRobots_HW1

## Project: Pose-Controlled Maze Race

Drive a LEGO Double Motor robot through a maze using real-time hand tracking
as the controller, instead of a physical remote. A webcam feed is processed
with MediaPipe to read hand gestures/positions each frame, which are turned
into motor commands sent over BLE via `legoeducation`.

### Stack
- **OpenCV** - webcam capture, color conversion, on-screen debug overlay
- **MediaPipe (Tasks API, `HandLandmarker`)** - per-frame hand landmark
  detection (21 points/hand). Note: the legacy `mp.solutions` API is gone as
  of mediapipe 1.0.1, so the project targets the Tasks API model bundles.
- **legoeducation** - `DoubleMotor` control, specifically `movement_move_tank()`
  for continuous differential-drive speed commands

### Control Architecture
- **Level-triggered, not edge-triggered**: every control tick, motor output is
  recomputed directly from whatever gesture is currently held. No "start"/"stop"
  events to track - if no hand is detected or the gesture is ambiguous, the
  fail-safe default is stop.
- **Two hands, two independent roles**:
  - **Left hand -> throttle** (shape-based gesture)
  - **Right hand -> turning** (position-based, not shape-based)
- **Differential drive mixing formula** combines both into wheel speeds each
  tick:
  ```
  speed_left  = throttle + turn
  speed_right = throttle - turn
  ```
  sent via `movement_move_tank(speed_left, speed_right, blocking=False)`.
- Turn value's sign gives direction (left/right) and magnitude gives
  intensity - small offset from frame center = gradual bend, large offset =
  turn-on-a-dime pivot. Same formula produces both; no separate turn "modes."
- **Debounce**: require a gesture to hold for several consecutive frames
  before it's accepted as the new state, to avoid jitter from per-frame
  misclassification.

### Gesture Vocabulary (v1)

| Hand  | Role     | Signal type | Gesture         | Meaning                |
|-------|----------|-------------|-----------------|------------------------|
| Left  | Throttle | Shape       | Open hand       | Forward                |
| Left  | Throttle | Shape       | Fist            | Neutral / stop         |
| Left  | Throttle | Shape       | Thumbs-out      | Backward               |
| Right | Turning  | Position    | Far left of center  | Pivot left         |
| Right | Turning  | Position    | Slightly left of center | Bend left      |
| Right | Turning  | Position    | Centered        | Straight                |
| Right | Turning  | Position    | Slightly right of center | Bend right    |
| Right | Turning  | Position    | Far right of center | Pivot right        |

Future add-on (not v1): make throttle proportional to hand openness/raise
height instead of a fixed discrete value.

### Shape Classification Approach
Open hand / fist / thumbs-out are distinguished using fingertip landmark
positions relative to the palm/wrist:
- **Extended vs. curled finger**: compare each fingertip landmark's distance
  from the wrist (or its position relative to its own knuckle) - curled
  fingers sit close to the palm, extended fingers sit far from it.
- **Open hand**: all (or most) fingers extended.
- **Fist**: all fingers curled.
- **Thumbs-out**: thumb extended while the other four fingers are curled.

### Implementation Checklist
- [ ] Hand shape classifier (open / fist / thumbs-out) from left-hand
      landmarks using fingertip-to-wrist distance
- [ ] Position-based turn signal from right-hand landmarks (offset from
      frame center -> direction + intensity)
- [ ] Debounce/hysteresis layer requiring N consecutive stable frames before
      accepting a new gesture state
- [ ] Differential drive mixing (`throttle`, `turn` -> `speed_left`,
      `speed_right`)
- [ ] Level-triggered control loop wired to `movement_move_tank()`
      (non-blocking) on the Double Motor
- [ ] Fail-safe default to stop when a hand is not detected or gesture is
      ambiguous
- [ ] End-to-end test: drive forward/backward/pivot/bend live via hand
      gestures
- [ ] (Future) Proportional throttle from hand openness/raise height
