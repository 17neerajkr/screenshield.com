import cv2
import mediapipe as mp
import time
import datetime
import numpy as np
from plyer import notification
import screen_brightness_control as sbc

try:
    import winsound
    def beep(): winsound.Beep(1000, 500)
except ImportError:
    def beep(): print("\a")

# Mediapipe setup
mp_face_mesh = mp.solutions.face_mesh

# Constants
KNOWN_EYE_DISTANCE = 6.3  # cm
FOCAL_LENGTH = 650
BLINK_THRESHOLD = 0.23
NO_BLINK_INTERVAL = 20
FACE_TIMEOUT = 30
EXERCISE_INTERVAL = 20 * 60
SCREEN_REMINDER_INTERVAL = 60 * 60
CONCENTRATION_CHECK_INTERVAL = 600

LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

# Shared state
_running = False   # controlled from GUI


def get_eye_aspect_ratio(landmarks, eye_indices):
    p = [landmarks[i] for i in eye_indices]
    vert1 = ((p[1].x - p[4].x) ** 2 + (p[1].y - p[4].y) ** 2) ** 0.5
    vert2 = ((p[0].x - p[3].x) ** 2 + (p[0].y - p[3].y) ** 2) ** 0.5
    horiz = ((p[2].x - p[5].x) ** 2 + (p[2].y - p[5].y) ** 2) ** 0.5
    return (vert1 + vert2) / (2.0 * horiz) if horiz != 0 else 0


def estimate_ambient_light(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)


def adjust_brightness(distance_cm, ambient_light):
    if ambient_light < 50:
        brightness = 40
    elif 50 <= ambient_light <= 100:
        brightness = 60
    else:
        brightness = 85
    try:
        sbc.set_brightness(brightness)
    except:
        pass
    return brightness


def run_main_logic():
    """Start the webcam detection loop. Controlled via _running flag."""
    global _running
    _running = True

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        notification.notify(title="Webcam Error", message="Webcam not accessible.", timeout=4)
        return

    with mp_face_mesh.FaceMesh(refine_landmarks=True) as face_mesh:
        blink_count = 0
        blink_per_minute = 0
        bpm_start_time = time.time()
        last_blink_time = time.time()
        last_exercise_time = time.time()
        last_face_detected = time.time()
        screen_start_time = time.time()
        paused = False
        pause_frame = None
        night_mode_triggered = False
        concentration_timer = 0
        distraction_count = 0

        while _running:
            ret, frame = cap.read()
            if not ret:
                continue

            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            current_hour = datetime.datetime.now().hour

            # Night mode
            if current_hour >= 19 and not night_mode_triggered:
                sbc.set_brightness(30)
                notification.notify(title="Night Mode", message="Brightness set to 30% for night use.", timeout=4)
                night_mode_triggered = True

            face_present = False
            if results.multi_face_landmarks:
                face_present = True
                last_face_detected = time.time()

                for face_landmarks in results.multi_face_landmarks:
                    left_eye = face_landmarks.landmark[33]
                    right_eye = face_landmarks.landmark[263]
                    x1, y1 = int(left_eye.x * w), int(left_eye.y * h)
                    x2, y2 = int(right_eye.x * w), int(right_eye.y * h)
                    pixel_distance = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                    distance_cm = (KNOWN_EYE_DISTANCE * FOCAL_LENGTH) / pixel_distance

                    if distance_cm < 40 and not paused:
                        notification.notify(title="Too Close!", message="Please move back.", timeout=5)
                        beep()
                        paused = True
                        pause_frame = frame.copy()
                    elif paused and distance_cm >= 45:
                        notification.notify(title="Safe Distance", message="You're now at a safe distance.", timeout=3)
                        paused = False

                    left_ear = get_eye_aspect_ratio(face_landmarks.landmark, LEFT_EYE_IDX)
                    right_ear = get_eye_aspect_ratio(face_landmarks.landmark, RIGHT_EYE_IDX)
                    avg_ear = (left_ear + right_ear) / 2.0

                    if avg_ear < BLINK_THRESHOLD:
                        blink_count += 1
                        blink_per_minute += 1
                        last_blink_time = time.time()

                    if time.time() - last_blink_time > NO_BLINK_INTERVAL:
                        notification.notify(title="Blink Reminder", message="You haven't blinked in a while.", timeout=5)
                        beep()
                        last_blink_time = time.time()

            if not face_present and time.time() - last_face_detected > FACE_TIMEOUT:
                notification.notify(title="No Face Detected", message="Please return to screen or take a break.", timeout=6)
                beep()
                last_face_detected = time.time()

            if time.time() - bpm_start_time >= 60:
                if blink_per_minute < 17:
                    notification.notify(title="Low Blink Rate", message="Blink more to prevent eye strain.", timeout=6)
                    beep()
                blink_per_minute = 0
                bpm_start_time = time.time()

            if time.time() - last_exercise_time > EXERCISE_INTERVAL:
                notification.notify(title="Eye Exercise", message="20-20-20 Rule: Look 20ft away for 20 seconds.", timeout=8)
                beep()
                last_exercise_time = time.time()

            if time.time() - screen_start_time > SCREEN_REMINDER_INTERVAL:
                notification.notify(title="Screen Time Alert", message="1 hour of screen usage completed.", timeout=6)
                screen_start_time = time.time()

            if face_present:
                concentration_timer += 1
            else:
                distraction_count += 1

            if concentration_timer % CONCENTRATION_CHECK_INTERVAL == 0 and concentration_timer > 0:
                status = "Good Focus" if distraction_count < 3 else "You seem distracted"
                notification.notify(title="Concentration Check", message=status, timeout=5)
                distraction_count = 0

            ambient = estimate_ambient_light(frame)
            brightness_level = adjust_brightness(40, ambient)

            cv2.putText(frame, f"Blinks: {blink_count}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(frame, f"Brightness: {brightness_level}%", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 255, 200), 2)
            cv2.putText(frame, f"Ambient: {int(ambient)}", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 200, 200), 2)

            if paused and pause_frame is not None:
                overlay = pause_frame.copy()
                cv2.putText(overlay, "⚠ SCREEN PAUSED - MOVE BACK ⚠", (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                cv2.imshow("ScreenShield", overlay)
            else:
                cv2.imshow("ScreenShield", frame)

            if cv2.waitKey(1) & 0xFF == 27:  # ESC key
                break

        cap.release()
        cv2.destroyAllWindows()


def stop_main_logic():
    """Stop the webcam detection loop."""
    global _running
    _running = False
