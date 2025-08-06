import sqlite3
import matplotlib.pyplot as plt

def show_graph():
    conn = sqlite3.connect("health.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, distance, blink_count FROM health_data")
    data = c.fetchall()
    conn.close()

    if not data:
        print("No data to plot.")
        return

    timestamps = [row[0] for row in data]
    distances = [row[1] for row in data]
    blinks = [row[2] for row in data]

    plt.figure(figsize=(10, 4))
    plt.plot(timestamps, distances, marker='o', label='Screen Distance (cm)')
    plt.plot(timestamps, blinks, marker='s', label='Blink Count')

    plt.xlabel('Time')
    plt.xticks(rotation=45, ha='right')
    plt.ylabel('Values')
    plt.title('Screen Distance and Blink Count Over Time')
    plt.legend()
    plt.tight_layout()
    plt.show()


def show_graph_screen():
    return None