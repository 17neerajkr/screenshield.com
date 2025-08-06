from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.switch import Switch
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from threading import Thread
from kivy.uix.widget import Widget
import time
import cv2
import mediapipe as mp
import screen_brightness_control as sbc
from plyer import notification
import pyttsx3
import winsound


# Initialize TTS
engine = pyttsx3.init()

def voice_alert(text):
    engine.say(text)
    engine.runAndWait()


class ScreenShieldUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=5, spacing=18, **kwargs)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))

        # Header
        header_box = BoxLayout(orientation="vertical", size_hint=(1, None), height=180, spacing=10, padding=(10, 50, 10, 20))
        header_title = Label(text="\U0001F6E1 ScreenShield", font_size="34sp", bold=True, halign="center", size_hint=(1, None), height=50)
        header_box.add_widget(header_title)

        # Master switch
        enable_box = BoxLayout(orientation="horizontal", size_hint=(1, None), height=50, spacing=10, padding=(10, 5))
        enable_box.add_widget(Label(text="Enable ScreenShield", font_size="20sp"))
        self.master_switch = Switch(active=False)
        self.master_switch.bind(active=self.on_master_switch)
        enable_box.add_widget(self.master_switch)
        header_box.add_widget(enable_box)

        self.status_label = Label(text="Status: OFF", font_size="18sp", color=(1, 0, 0, 1), size_hint=(1, None), height=30)
        header_box.add_widget(self.status_label)

        self.add_widget(header_box)

        # Features
        self.feature_switches = {}
        features = [
            "Brightness Control", "Blink Detection", "Distance Alert", "Notifications",
            "Beep Sound", "Screen Pause", "Voice Alerts", "Minimal Mode", "Eye Exercise Reminders"
        ]
        for feat in features:
            row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=40, padding=(10, 5), spacing=10)
            row.add_widget(Label(text=feat, font_size="17sp"))
            sw = Switch(active=True)
            sw.bind(active=self.on_feature_toggle)
            self.feature_switches[feat] = sw
            row.add_widget(sw)
            self.add_widget(row)

        # Distance Slider
        self.add_widget(Label(text="Set Safe Distance (cm):", font_size="18sp"))
        slider_box = BoxLayout(orientation="horizontal", size_hint=(1, None), height=30, spacing=10, padding=(8, 0))
        self.distance_slider = Slider(min=5, max=50, value=30, step=1)
        self.distance_slider.bind(value=self.on_distance_slider_change)
        slider_box.add_widget(self.distance_slider)
        self.distance_input = TextInput(text="30", multiline=False, size_hint=(None, None), size=(60, 40), input_filter='int')
        self.distance_input.bind(text=self.on_distance_input_change)
        slider_box.add_widget(self.distance_input)
        self.add_widget(slider_box)
        self.distance_label = Label(text="Current: 30 cm", font_size="18sp")
        self.add_widget(self.distance_label)

        # Live distance
        self.add_widget(Widget(size_hint_y=None, height=1))
        self.live_distance_label = Label(text="Live Distance: -- cm", font_size="18sp", color=(1, 1, 1, 1))
        self.add_widget(self.live_distance_label)

        # Timer
        self.add_widget(Widget(size_hint_y=None, height=2))
        self.timer_label = Label(text="Session Time: 0 min", font_size="18sp")
        self.add_widget(self.timer_label)

        # Progress bar
        self.exercise_bar = ProgressBar(max=20, value=0, size_hint=(1, None), height=10)
        self.add_widget(self.exercise_bar)

        # Buttons
        buttons_box = BoxLayout(orientation="horizontal", size_hint=(1, None), height=70, spacing=25)
        self.start_btn = Button(text="▶ Start", font_size="20sp", background_color=(0.2, 0.6, 0.9, 1), size_hint=(0.3, None), height=77)
        self.start_btn.bind(on_press=self.toggle_monitoring)
        buttons_box.add_widget(self.start_btn)

        self.reset_btn = Button(text="⟳ Reset", font_size="20sp", background_color=(0.9, 0.4, 0.3, 1), size_hint=(0.3, None), height=77)
        self.reset_btn.bind(on_press=self.reset_defaults)
        buttons_box.add_widget(self.reset_btn)

        self.exit_btn = Button(text="✖ Exit", font_size="20sp", background_color=(1, 0, 0, 1), size_hint=(0.3, None), height=77)
        self.exit_btn.bind(on_press=self.stop_now)
        buttons_box.add_widget(self.exit_btn)

        self.add_widget(buttons_box)

        # App state
        self.running = False
        self.thread = None
        self.start_time = None
        self.alert_count = 0
        self.max_alerts = 2
        self.distance_threshold = int(self.distance_slider.value)
        self.total_minutes = 0
        self.progress_counter = 0
        self.mp_face_mesh = mp.solutions.face_mesh

        # Clock-based updates
        Clock.schedule_interval(self.update_timer, 60)
        Clock.schedule_interval(self.update_exercise_bar, 1)

    def on_distance_slider_change(self, instance, value):
        self.distance_label.text = f"Current: {int(value)} cm"
        self.distance_input.text = str(int(value))
        self.distance_threshold = int(value)

    def on_distance_input_change(self, instance, text):
        if text.isdigit():
            val = int(text)
            if 5 <= val <= 50:
                self.distance_slider.value = val
                self.distance_threshold = val
                self.distance_label.text = f"Current: {val} cm"

    def on_master_switch(self, instance, value):
        self.status_label.text = "Status: ON" if value else "Status: OFF"
        self.status_label.color = (0, 1, 0, 1) if value else (1, 0, 0, 1)
        for sw in self.feature_switches.values():
            sw.disabled = not value

    def on_feature_toggle(self, switch, value):
        pass  # Placeholder for future handling

    def toggle_monitoring(self, instance):
        if not self.master_switch.active:
            notification.notify(title="ScreenShield Alert", message="Please enable ScreenShield before starting.", timeout=3)
            voice_alert("Please enable ScreenShield before starting.")
            return

        if self.running:
            self.running = False
            self.start_btn.text = "▶ Start"
            return

        self.running = True
        self.alert_count = 0
        self.total_minutes = 0
        self.progress_counter = 0
        self.timer_label.text = "Session Time: 0 min"
        self.exercise_bar.value = 0
        self.start_btn.text = "⏸ Stop"
        self.thread = Thread(target=self.monitor_user)
        self.thread.start()

    def monitor_user(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            notification.notify(title="Webcam Error", message="Webcam not accessible.", timeout=4)
            voice_alert("Webcam could not be accessed. Please check your camera.")
            return

        with self.mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5) as face_mesh:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)
                if results.multi_face_landmarks:
                    nose = results.multi_face_landmarks[0].landmark[1]
                    distance_cm = round((1 - nose.z) * 50, 1)
                    Clock.schedule_once(lambda dt: self.update_distance_display(distance_cm))
                    if self.alert_count < self.max_alerts:
                        if distance_cm < 25:
                            self.trigger_alert(distance_cm, "red")
                        elif distance_cm < 30:
                            self.trigger_alert(distance_cm, "yellow")
                time.sleep(0.5)

        cap.release()

    def update_distance_display(self, dist):
        self.live_distance_label.text = f"Live Distance: {dist:.1f} cm"
        if dist < 25:
            self.live_distance_label.color = (1, 0, 0, 1)
        elif dist < 30:
            self.live_distance_label.color = (1, 1, 0, 1)
        else:
            self.live_distance_label.color = (0, 1, 0, 1)

    def trigger_alert(self, dist, level):
        self.alert_count += 1
        if self.feature_switches["Notifications"].active:
            msg = "Too Close!" if level == "red" else "Caution Zone"
            notification.notify(title=msg, message=f"You are {dist} cm from the screen.", timeout=3)
        if self.feature_switches["Voice Alerts"].active:
            voice_alert(f"You are {dist} centimeters from the screen.")
        if self.feature_switches["Beep Sound"].active:
            winsound.Beep(1000 if level == "red" else 800, 500)
        if self.feature_switches["Brightness Control"].active:
            try:
                sbc.set_brightness(30 if level == "red" else 50)
            except:
                pass

    def reset_defaults(self, instance):
        self.master_switch.active = False
        self.distance_slider.value = 30
        self.distance_input.text = "30"
        self.exercise_bar.value = 0
        self.timer_label.text = "Session Time: 0 min"
        self.live_distance_label.text = "Live Distance: -- cm"
        self.alert_count = 0
        for sw in self.feature_switches.values():
            sw.active = True

    def stop_now(self, instance):
        self.running = False
        App.get_running_app().stop()

    def update_timer(self, dt):
        if self.running:
            self.total_minutes += 1
            self.timer_label.text = f"Session Time: {self.total_minutes} min"

    def update_exercise_bar(self, dt):
        if self.running:
            self.progress_counter += 1
            if self.progress_counter <= 20:
                self.exercise_bar.value = self.progress_counter
            else:
                self.progress_counter = 0
                self.exercise_bar.value = 0
                if self.feature_switches["Eye Exercise Reminders"].active:
                    notification.notify(title="Eye Exercise Reminder", message="Please take a 20-second eye break.", timeout=3)
                    if self.feature_switches["Voice Alerts"].active:
                        voice_alert("Please take a 20-second eye break.")


class ScreenShieldApp(App):
    def build(self):
        return ScreenShieldUI()


if __name__== '__main__':
    ScreenShieldApp().run()
