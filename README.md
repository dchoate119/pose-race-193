# MobileRobots_HW1

## Project: Pose-Controlled Maze Race

Drive a LEGO Double Motor robot through a maze using real-time hand tracking
as the controller, instead of a physical remote. A webcam feed is processed
with MediaPipe to read hand gestures/positions each frame, which are turned
into motor commands sent over BLE via `legoeducation`.

# Key files:
1. main.py: drives car based on gestures
2. control.py: Defines the control system
3. gestures.py: Maps key points in hand in 2D space

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
  events to track - if no hand is detected, throttle is 0, so the fail-safe
  default is stop.
- **Single hand, one signal drives throttle, another drives steering**:
  - **How open the hand is -> throttle** (continuous, closed fist = 0%,
    fully open = 100%)
  - **Horizontal position -> turn direction/intensity** (position-based, not
    shape-based)
  - **A box at the bottom of frame -> reverse** (drop the hand low to back up)
- **Differential drive mixing formula** combines both into wheel speeds each
  tick:
  ```
  speed_left  = throttle + turn
  speed_right = throttle - turn
  ```
  sent via `movement_move_tank(speed_left, speed_right, blocking=False)`.
  Turn is itself scaled by openness, so a closed fist always stops fully
  instead of spinning in place in a turn zone.
- Turn value's sign gives direction (left/right) and magnitude gives
  intensity - small offset from frame center = gradual bend, large offset =
  turn-on-a-dime pivot. Same formula produces both; no separate turn "modes."
- **Debounce**: require a turn zone to hold for several consecutive frames
  before it's accepted as the new state, to avoid jitter from per-frame
  misclassification.

### Control Vocabulary (v2 - single hand)

| Signal              | Type       | Value              | Meaning                    |
|----------------------|------------|--------------------|-----------------------------|
| Hand openness        | Shape      | Closed fist -> open | 0% -> 100% throttle        |
| Horizontal position  | Position   | Far left of center | Pivot left                 |
| Horizontal position  | Position   | Slightly left of center | Bend left              |
| Horizontal position  | Position   | Centered            | Straight                   |
| Horizontal position  | Position   | Slightly right of center | Bend right            |
| Horizontal position  | Position   | Far right of center | Pivot right                |
| Vertical position     | Position   | Below the backward box threshold | Reverse (openness still sets speed) |

### Openness Classification Approach
Throttle is a continuous 0.0-1.0 value from fingertip landmark positions
relative to the palm/wrist:
- For each of the four fingers, compare the fingertip's distance from the
  wrist to its own knuckle's distance from the wrist - curled fingers sit
  close (ratio near 1), extended fingers sit far (ratio higher).
- Average that ratio across the four fingers and linearly map it between a
  closed-fist ratio and a fully-open ratio, clamped to [0, 1].

### Implementation Checklist
- [x] Continuous openness -> throttle from hand landmarks (fingertip-to-wrist
      distance ratio)
- [x] Position-based turn zone from wrist landmarks (offset from frame
      center -> direction + intensity)
- [x] Backward box from wrist vertical position, independent of throttle
- [x] Debounce/hysteresis layer requiring N consecutive stable frames before
      accepting a new turn zone
- [x] Differential drive mixing (`throttle`, `turn` -> `speed_left`,
      `speed_right`), turn scaled by throttle so a closed fist fully stops
- [x] Level-triggered control loop wired to `movement_move_tank()`
      (non-blocking) on the Double Motor
- [x] Fail-safe default to stop when a hand is not detected
- [ ] End-to-end test: drive forward/backward/pivot/bend live via one hand
