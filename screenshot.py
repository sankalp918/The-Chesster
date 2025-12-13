import os
import time
import pyautogui

# Open Firefox and navigate to chess.com
os.system("start firefox https://www.chess.com/home")
time.sleep(10)

# Click "Play Bots" button
button_location = pyautogui.locateOnScreen('Play_Bots.png', confidence=0.8)
if button_location is not None:
    button_point = pyautogui.center(button_location)
    pyautogui.click(button_point)
    time.sleep(3)
else:
    print("Play Bots button not found on screen.")
    exit()

# Click "Play" button to start game with default bot
button_location = pyautogui.locateOnScreen('Play.png', confidence=0.8)
if button_location is not None:
    button_point = pyautogui.center(button_location)
    pyautogui.click(button_point)
    time.sleep(5)
else:
    print("Play button not found on screen.")
    exit()

# After game starts, hand off to ChessBot logic
try:
    from chess_engine import ChessBot
    bot = ChessBot(stockfish_path='stockfish.exe', search_depth=15)
    bot.play_game()
except Exception as e:
    print(f"Failed to start ChessBot: {e}")
