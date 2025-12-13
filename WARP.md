# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

The-Chesster is a chess engine automation project that plays on chess.com on behalf of the player. Currently in early development stage.

**Current State:**
- Only automation/screenshot functionality implemented (`screenshot.py`)
- Core chess engine (minimax with alpha-beta pruning) not yet implemented
- Uses pyautogui for browser automation and image recognition to interact with chess.com

**Planned Architecture:**
- Chess engine using minimax algorithm with alpha-beta pruning
- Board state evaluation function
- Integration with python-chess library for board representation and move generation
- Configurable search depth, evaluation functions, and time limits

## Commands

### Running the Automation
```powershell
python screenshot.py
```

### Dependencies
```powershell
pip install pyautogui pygetwindow pillow opencv-python python-chess stockfish numpy keyboard
```

**Note:** OpenCV is required for `confidence` parameter in image recognition. `python-chess` and the `stockfish` wrapper are used for engine analysis. `numpy` is used for board-diff detection.

## Critical Constraints

**Screenshot Resolution:** The project cannot take proper screenshots if Windows display resolution scale is more than 100%. Image recognition with `pyautogui.locateOnScreen()` requires exact pixel matching, so system scaling breaks the confidence matching.

**Image Assets:** The automation relies on two screenshot images:
- `Play_Bots.png` - Button to access bot play section
- `Play.png` - Start game button (plays against default bot)

These must be recaptured if the UI changes or display settings differ.

## Development Notes

**Current Branch:** `screenshots_taken` (ahead of main)

**Automation Flow:**
1. Opens Firefox with chess.com
2. Waits 10s for page load
3. Clicks "Play Bots" button
4. Clicks "Play" button to start game with default bot
5. Delays: 3s after Play Bots, 5s after Play (wait for board load)

**Board Calibration:** After the board loads, hover the mouse at the top-left corner and press Ctrl+Alt+1, then hover bottom-right and press Ctrl+Alt+2. No window switching is required.

**Future Implementation Areas:**
- Chess engine core (minimax/alpha-beta)
- Board state parsing from chess.com
- Move generation and execution
- Evaluation function
- Opening book integration
- Human vs engine modes
