import os
import time
import pyautogui
import pygetwindow as gw
import PIL


# Take a screenshot of a part of the screen where chess board is located.
def screenshot():
    # Get the window size
    window = gw.getWindowsWithTitle('Play chess online')[0]
    # Activating the window and resizing it
    window.activate()
    window.resizeTo(800, 600)
    window.moveTo(0, 0)
    time.sleep(1)
    # Get the active window's position
    x, y, w, h = window.left, window.top, window.width, window.height
    # Take a screenshot of the active window
    screenshot_captured = pyautogui.screenshot(region=(x, y, w, h))
    # Crop the screenshot to the chess board
    screenshot_cropped = screenshot_captured.crop((x + 252, y + 220, x + 558, y + 522))
    # Save the screenshot to pictures folder with a timestamp
    screenshot_cropped.save(os.path.join(os.path.expanduser("~"), "Pictures", f"{time.time()}.png"))


screenshot()
