import cv2
import mediapipe as mp
import time
import datetime
import speech_recognition as sr
from plyer import notification
import screen_brightness_control as sbc
import threading
import platformgit

try:
    import winsound
    def beep():
        winsound.Beep(1000, 500)
except ImportError:
    def beep():
        print("\a")

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True)
cap = cv2.VideoCapture(0)

KNOWN_EYE_DISTANCE = 6.3
FOCAL_LENGTH = 650

paused = False
pause_frame = None
blink_count = 0
blink_log = []
last_blink_time = time.time()
last_appearance_time = time.time()
last_focus_time = time.time()
last_reminder_time = time.time()
last_eye_exercise_time = time.time()
last_reset_time = time.time()

BLINK_THRESHOLD = 0.23
NO_BLINK_INTERVAL = 20
REMINDER_INTERVAL = 3600
EYE_EXERCISE_INTERVAL = 20 * 60
RESET_INTERVAL = 600
MAX_NOTIFICATIONS = 3
notification_count = 0
FACE_ABSENCE_LIMIT = 10

LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

low_blink_notified = False
no_blink_beeped = False
face_absence_notified = False

def get_eye_aspect_ratio(landmarks, eye_indices):
    p = [landmarks[i] for i in eye_indices]
    vert1 = ((p[1].x - p[5].x) ** 2 + (p[1].y - p[5].y) ** 2) ** 0.5
    vert2 = ((p[2].x - p[4].x) ** 2 + (p[2].y - p[4].y) ** 2) ** 0.5
    horiz = ((p[0].x - p[3].x) ** 2 + (p[0].y - p[3].y) ** 2) ** 0.5
    return (vert1 + vert2) / (2.0 * horiz) if horiz else 0

def adjust_brightness(distance_cm):
    global notification_count, last_reset_time
    if time.time() - last_reset_time > RESET_INTERVAL:
        notification_count = 0
        last_reset_time = time.time()

    hour = datetime.datetime.now().hour
    if hour >= 19:
        brightness = 30
    elif distance_cm < 35:
        brightness = 35
    elif 35 <= distance_cm <= 50:
        brightness = 60
    else:
        brightness = 85

    try:
        sbc.set_brightness(brightness)
    except Exception:
        pass

    if notification_count < MAX_NOTIFICATIONS:
        notification.notify(
            title="ScreenShield Brightness",
            message=f"Adjusted brightness to {brightness}%",
            timeout=4
        )
        notification_count += 1

    return brightness

def check_blink_rate():
    global low_blink_notified
    current_time = time.time()
    one_minute_ago = current_time - 60
    recent_blinks = [b for b in blink_log if b >= one_minute_ago]
    if len(recent_blinks) < 17 and not low_blink_notified:
        notification.notify(
            title="Low Blink Rate",
            message="You blinked less than 17 times in the last minute.",
            timeout=5
        )
        beep()
        low_blink_notified = True
    elif len(recent_blinks) >= 17:
        low_blink_notified = False

def eye_exercise_reminder():
    notification.notify(
        title="Eye Exercise Reminder",
        message="20 minutes passed. Look at something 20 feet away for 20 seconds.",
        timeout=6
    )
    beep()

def listen_for_commands():
    r = sr.Recognizer()
    mic = sr.Microphone()
    while True:
        with mic as source:
            r.adjust_for_ambient_noise(source)
            try:
                audio = r.listen(source, timeout=5)
                command = r.recognize_google(audio).lower()
                if "pause" in command:
                    globals()['paused'] = True
                elif "continue" in command:
                    globals()['paused'] = False
                elif "exercise" in command:
                    eye_exercise_reminder()
                elif "status" in command:
                    check_blink_rate()
            except Exception:
                continue

threading.Thread(target=listen_for_commands, daemon=True).start()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)
    current_time = time.time()
    face_detected = False

    if results.multi_face_landmarks:
        face_detected = True
        last_appearance_time = current_time
        face_absence_notified = False

        for face_landmarks in results.multi_face_landmarks:
            left_eye = face_landmarks.landmark[33]
            right_eye = face_landmarks.landmark[263]
            x1, y1 = int(left_eye.x * w), int(left_eye.y * h)
            x2, y2 = int(right_eye.x * w), int(right_eye.y * h)

            cv2.circle(frame, (x1, y1), 5, (0, 255, 0), -1)
            cv2.circle(frame, (x2, y2), 5, (0, 255, 0), -1)
            pixel_distance = ((x2 - x1)*2 + (y2 - y1)*2) ** 0.5
            distance_cm = (KNOWN_EYE_DISTANCE * FOCAL_LENGTH) / pixel_distance

            if distance_cm < 40:
                cv2.putText(frame, "Too Close!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                if not paused:
                    notification.notify(title="Too Close!", message="Move back from screen", timeout=5)
                    beep()
                    paused = True
                    pause_frame = frame.copy()
            elif paused and distance_cm >= 45:
                notification.notify(title="Safe Distance", message="You're at a safe distance now.", timeout=3)
                paused = False

            if not paused:
                status = "A Bit Close" if 40 <= distance_cm <= 45 else "Safe"
                color = (0, 255, 255) if status == "A Bit Close" else (0, 255, 0)
                cv2.putText(frame, f"Distance: {int(distance_cm)} cm - {status}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

            left_ear = get_eye_aspect_ratio(face_landmarks.landmark, LEFT_EYE_IDX)
            right_ear = get_eye_aspect_ratio(face_landmarks.landmark, RIGHT_EYE_IDX)
            avg_ear = (left_ear + right_ear) / 2.0

            if avg_ear < BLINK_THRESHOLD:
                blink_count += 1
                blink_log.append(current_time)
                last_blink_time = current_time
                cv2.putText(frame, "Blink Detected", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                no_blink_beeped = False

            if current_time - last_blink_time > NO_BLINK_INTERVAL and not no_blink_beeped:
                notification.notify(title="Dry Eye Alert", message="You haven't blinked in a while. Blink!", timeout=5)
                beep()
                no_blink_beeped = True

            if current_time - last_reminder_time > REMINDER_INTERVAL:
                notification.notify(title="Screen Time Reminder", message="You've been looking at the screen for 1 hour.", timeout=5)
                beep()
                last_reminder_time = current_time

            if current_time - last_eye_exercise_time > EYE_EXERCISE_INTERVAL:
                eye_exercise_reminder()
                last_eye_exercise_time = current_time

            brightness = adjust_brightness(distance_cm)
            cv2.putText(frame, f"Brightness: {brightness}%", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 255, 200), 2)

            concentration_duration = int(current_time - last_focus_time)
            if concentration_duration < 60:
                status_text = "Good Concentration"
                status_color = (0, 255, 0)
            elif 60 <= concentration_duration < 180:
                status_text = "Fair Concentration"
                status_color = (0, 255, 255)
            else:
                status_text = "Distraction Detected"
                status_color = (0, 0, 255)

            cv2.putText(frame, status_text, (50, 400), cv2.FONT_HERSHEY_SIMPLEX, 1.1, status_color, 3)
            last_focus_time = current_time

        check_blink_rate()

    elif not face_detected and time.time() - last_appearance_time > FACE_ABSENCE_LIMIT and not face_absence_notified:
        notification.notify(title="Face Not Detected", message="User is away from screen.", timeout=4)
        paused = True
        face_absence_notified = True

    if paused and pause_frame is not None:
        warning = pause_frame.copy()
        cv2.putText(warning, "⚠ SCREEN PAUSED - MOVE BACK ⚠", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
        cv2.imshow("ScreenShield", warning)
    else:
        cv2.imshow("ScreenShield", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()