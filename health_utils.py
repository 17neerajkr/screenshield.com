import sqlite3

def save_data(timestamp, distance, blink_count):
    conn = sqlite3.connect("health.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS health_data (
                    timestamp TEXT,
                    distance INTEGER,
                    blink_count INTEGER
                )''')
    c.execute("INSERT INTO health_data VALUES (?, ?, ?)", (timestamp, distance, blink_count))
    conn.commit()
    conn.close()

def get_health_tip(distance, blink_count):
    if distance < 40:
        return "You're too close to the screen. Move back!"
    elif blink_count < 10:
        return "Blink more to reduce eye strain."
    else:
        return "Good job! Keep maintaining your posture and blink rate."
