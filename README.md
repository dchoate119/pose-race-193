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

### Control Architecture (v2, simplified)
- **Level-triggered, not edge-triggered**: every control tick, motor output is
  recomputed directly from whatever is currently seen. No "start"/"stop"
  events to track - if no hand is detected, both hands are detected, or the
  gesture is ambiguous, the fail-safe default is stop.
- **One hand, two signals at once**:
  - **Shape -> throttle**: open hand = forward, fist = backward.
  - **Horizontal position -> turn**: continuous, proportional to the hand's
    offset from frame center (no discrete zones). Turn is independent of
    shape - it's live off hand position any time exactly one hand is visible.
  - **Both hands visible -> stop**: an explicit safety override, checked
    before shape/position classification.
- **Differential drive mixing formula** combines both into wheel speeds each
  tick:
  ```
  speed_left  = throttle + turn
  speed_right = throttle - turn
  ```
  sent via `movement_move_tank(speed_left, speed_right, blocking=False)`.
- **Debounce**: the throttle shape must hold for several consecutive frames
  before it's accepted as the new state, to avoid jitter from per-frame
  misclassification. Turn doesn't need this since it's a continuous value,
  not a discrete state.

This replaces the original v1 design (left hand = throttle shape, right hand
= turn position, 5-zone discrete turning) with a single-hand controller -
simpler to reason about and to hold steady while driving.

### Gesture Vocabulary (v2)

| Signal   | Type       | Gesture / Position           | Meaning                    |
|----------|------------|-------------------------------|----------------------------|
| Throttle | Shape      | Open hand                     | Forward                    |
| Throttle | Shape      | Fist                           | Backward                   |
| Throttle | Shape      | Ambiguous (neither)            | Stop (fail-safe)           |
| Turn     | Position   | Offset from frame center       | Proportional turn speed, clamped at a max |
| -        | Hand count | Both hands visible             | Stop (safety override)     |
| -        | Hand count | No hand visible                | Stop (fail-safe)           |

Future add-on: make throttle proportional to hand openness/raise height
instead of a fixed discrete value.

### Shape Classification Approach
Open hand / fist are distinguished using fingertip landmark positions
relative to the palm/wrist:
- **Extended vs. curled finger**: compare each fingertip landmark's distance
  from the wrist to its own knuckle's distance from the wrist - curled
  fingers sit close to the palm, extended fingers sit far from it.
- **Open hand**: all (or most) fingers extended -> forward.
- **Fist**: all fingers curled -> backward.
- Anything in between is ambiguous/transitional and defaults to stop.

Turn no longer depends on shape at all: it's read directly from the wrist's
horizontal offset from center, since the wrist position stays stable
regardless of whether the hand is open or closed.

### Implementation Checklist
- [x] Hand shape classifier (open / fist) using fingertip-to-wrist distance
- [x] Continuous position-based turn signal (offset from frame center ->
      proportional turn speed, clamped)
- [x] Both-hands-visible safety stop override
- [x] Debounce/hysteresis layer requiring N consecutive stable frames before
      accepting a new throttle state
- [x] Differential drive mixing (`throttle`, `turn` -> `speed_left`,
      `speed_right`)
- [x] Level-triggered control loop wired to `movement_move_tank()`
      (non-blocking) on the Double Motor
- [x] Fail-safe default to stop when no hand, both hands, or an ambiguous
      gesture is seen
- [ ] End-to-end test: drive forward/backward/turn live via hand gestures
- [ ] (Future) Proportional throttle from hand openness/raise height
