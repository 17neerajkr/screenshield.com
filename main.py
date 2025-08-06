from code_gui import ScreenShieldApp
from logic_backend import run_main_logic
from health_utils import setup_health_monitor
from graph_utils import show_graph_screen
import threading
import time

def start_logic():
    time.sleep(2)  # Let GUI load first
    run_main_logic()

def start_health():
    setup_health_monitor()

def main():
    # Start health monitoring in background
    threading.Thread(target=start_health, daemon=True).start()

    # Start logic processing in background
    threading.Thread(target=start_logic, daemon=True).start()

    # Start the GUI App
    ScreenShieldApp().run()

    # After GUI closes, ask user to see graph
    user_input = input("Do you want to see usage stats as a graph? (yes/no): ").lower()
    if user_input in ['yes', 'y']:
        show_graph_screen()

if __name__ == '__main__':
    main()
