import chess
import chess.engine
import random
import time
import pyautogui
from PIL import Image, ImageChops
import numpy as np
import os
from datetime import datetime
import keyboard
import shutil

class ChessBot:
    def __init__(self, stockfish_path, search_depth=15):
        """
        Initialize the chess bot.
        
        Args:
            stockfish_path: Path to stockfish executable (e.g., 'stockfish.exe' or '/path/to/stockfish')
            search_depth: Depth for Stockfish analysis (default: 15)
        """
        self.board = chess.Board()
        self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        self.search_depth = search_depth
        self.playing_white = None
        self.previous_screenshot = None
        self.previous_screenshot_path = None
        self.board_region = None  # (x, y, w, h)
        self.square_size = None
        os.makedirs('boards', exist_ok=True)
        os.makedirs('boards\\debug', exist_ok=True)
        self.debug = os.getenv('CHESSTER_DEBUG', '0') == '1'
        
    # ---- Calibration & Capture ----
    def calibrate_board_region(self):
        print("Calibration: Hover mouse over TOP-LEFT of the board and press Ctrl+Alt+1 (no window switch needed).")
        keyboard.wait('ctrl+alt+1')
        x1, y1 = pyautogui.position()
        print("Now hover over BOTTOM-RIGHT of the board and press Ctrl+Alt+2.")
        keyboard.wait('ctrl+alt+2')
        x2, y2 = pyautogui.position()
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        # enforce square
        s = min(w, h)
        self.board_region = (x, y, s, s)
        self.square_size = s // 8
        print(f"Board region calibrated: {self.board_region}, square={self.square_size}px")

    def capture_board_screenshot(self, save=True, label="board"):
        """Capture a screenshot of the chess board area only.
        Returns (image, path_or_None).
        """
        if not self.board_region:
            self.calibrate_board_region()
        x, y, w, h = self.board_region
        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        save_path = None
        if save:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = os.path.join('boards', f"{label}_{ts}.png")
            screenshot.save(save_path)
        return screenshot, save_path

    # ---- Orientation Detection ----
    def detect_player_color(self):
        print("Detecting player color from first board image...")
        img, _ = self.capture_board_screenshot(save=True, label="start")
        s = self.square_size
        # Compare brightness on first two ranks vs last two ranks
        top2 = img.crop((0, 0, img.width, 2*s))
        bot2 = img.crop((0, img.height - 2*s, img.width, img.height))
        top_arr = np.asarray(top2.convert('L'), dtype=np.float32)
        bot_arr = np.asarray(bot2.convert('L'), dtype=np.float32)
        # Count "bright" pixels (likely white pieces/highlights)
        top_bright = float((top_arr > 200).sum())
        bot_bright = float((bot_arr > 200).sum())
        # Fallback metric: mean brightness
        top_mean = float(top_arr.mean())
        bot_mean = float(bot_arr.mean())
        vote_bright = bot_bright > top_bright
        vote_mean = bot_mean > top_mean
        self.playing_white = vote_bright or vote_mean
        print(f"top_bright={top_bright:.0f}, bot_bright={bot_bright:.0f}, top_mean={top_mean:.1f}, bot_mean={bot_mean:.1f} -> {'White' if self.playing_white else 'Black'}")
        # If the votes disagree narrowly, allow manual override with hotkeys
        diff_ratio = abs(bot_bright - top_bright) / max(1.0, max(bot_bright, top_bright))
        if diff_ratio < 0.02:  # too close to call
            print("Ambiguous orientation. Press Ctrl+Alt+W if you are White, Ctrl+Alt+B if Black (5s timeout).")
            t0 = time.time()
            while time.time() - t0 < 5:
                if keyboard.is_pressed('ctrl+alt+w'):
                    self.playing_white = True
                    break
                if keyboard.is_pressed('ctrl+alt+b'):
                    self.playing_white = False
                    break
        return self.playing_white

    # ---- Mapping helpers ----
    def _index_to_square(self, file_idx, rank_idx):
        """Map file/rank indices (0..7) to python-chess square given white at bottom."""
        # When white is at bottom, image row 0 is rank 8; row 7 is rank 1
        rank = 7 - rank_idx
        file = file_idx  # 0=a .. 7=h
        return chess.square(file, rank)

    def _square_center_xy(self, sq):
        """Return screen pixel center for a chess square (white orientation only)."""
        if not self.board_region:
            raise RuntimeError("Board region not calibrated")
        x, y, w, h = self.board_region
        s = self.square_size
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        # Convert back to image grid indices
        rank_idx = 7 - rank
        file_idx = file
        cx = x + file_idx * s + s // 2
        cy = y + rank_idx * s + s // 2
        return cx, cy

    # ---- Engine & Move selection ----
    def get_top_moves(self, num_moves=5):
        info = self.engine.analyse(
            self.board,
            chess.engine.Limit(depth=self.search_depth),
            multipv=num_moves
        )
        moves = [pv['pv'][0] for pv in info]
        return moves

    def make_white_move(self):
        print(f"Calculating move at depth {self.search_depth}...")
        top_moves = self.get_top_moves(5)
        selected_move = random.choice(top_moves)
        print(f"Top moves: {[m.uci() for m in top_moves]}")
        print(f"Selected move: {selected_move.uci()}")
        self.board.push(selected_move)
        self.execute_move_on_ui(selected_move)
        # Allow board animations to settle and capture stable baseline
        time.sleep(0.8)
        stable = None
        for _ in range(5):  # up to ~2s to settle
            img1, p1 = self.capture_board_screenshot(save=False)
            time.sleep(0.4)
            img2, _ = self.capture_board_screenshot(save=False)
            if self._images_similar(img1, img2):
                stable = img2
                break
        if stable is None:
            stable, _ = self.capture_board_screenshot(save=False)
        # Save stable image and replace previous baseline file
        new_img, new_path = self.capture_board_screenshot(save=True, label="after_our_move")
        if self.previous_screenshot_path and os.path.exists(self.previous_screenshot_path):
            try:
                os.remove(self.previous_screenshot_path)
            except OSError:
                pass
        self.previous_screenshot = new_img
        self.previous_screenshot_path = new_path
        print(f"Baseline updated after our move -> {os.path.basename(new_path) if new_path else 'memory only'}")
        return selected_move

    def execute_move_on_ui(self, move):
        print(f"Executing move {move.uci()} on UI...")
        if not self.playing_white:
            raise NotImplementedError("Only white orientation supported right now.")
        from_xy = self._square_center_xy(move.from_square)
        to_xy = self._square_center_xy(move.to_square)
        pyautogui.click(from_xy)
        time.sleep(0.05)
        pyautogui.click(to_xy)
        time.sleep(0.2)

    # ---- Opponent move detection ----
    def _rgb_to_gray_ignore_green(self, img: Image.Image) -> np.ndarray:
        arr = np.asarray(img.convert('RGB'), dtype=np.float32)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        # Strong green overlay mask (arrows/highlights)
        green_dom = (g > r * 1.25) & (g > b * 1.25) & (g > 110)
        # Yellow highlight mask (from-square / to-square)
        yellow_dom = (r > 150) & (g > 150) & (b < 120) & (np.abs(r - g) < 40)
        mask = green_dom | yellow_dom
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        if mask.any():
            gray[mask] = float(gray[~mask].mean())  # neutralize overlays
        return gray

    def _images_similar(self, img_a: Image.Image, img_b: Image.Image, eps: float = 4.0) -> bool:
        a = self._rgb_to_gray_ignore_green(img_a)
        b = self._rgb_to_gray_ignore_green(img_b)
        return float(np.mean(np.abs(a - b))) < eps

    def _per_square_diff(self, img_a: Image.Image, img_b: Image.Image):
        arr_a = self._rgb_to_gray_ignore_green(img_a)
        arr_b = self._rgb_to_gray_ignore_green(img_b)
        s = self.square_size
        diffs = np.zeros((8, 8), dtype=np.float32)
        for r in range(8):
            for c in range(8):
                y0, y1 = r * s, (r + 1) * s
                x0, x1 = c * s, (c + 1) * s
                block_a = arr_a[y0:y1, x0:x1]
                block_b = arr_b[y0:y1, x0:x1]
                diffs[r, c] = float(np.mean(np.abs(block_a - block_b)))
        return diffs

    def _square_to_index(self, sq: chess.Square):
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        r = 7 - rank  # image row index
        c = file       # image col index
        return r, c

    def _save_diff_debug(self, diffs: np.ndarray):
        if not self.debug:
            return
        # Scale to 0..255 and save as 8x8 nearest-neighbor blown up to board size
        d = diffs.copy()
        d -= d.min()
        if d.max() > 0:
            d = d / d.max()
        img = Image.fromarray((d * 255).astype('uint8'), mode='L')
        big = img.resize((self.square_size * 8, self.square_size * 8), resample=Image.NEAREST)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        big.save(os.path.join('boards', 'debug', f'diff_{ts}.png'))

    def detect_opponent_move(self, prev_img: Image.Image, curr_img: Image.Image):
        diffs = self._per_square_diff(prev_img, curr_img)
        self._save_diff_debug(diffs)
        # Score all legal moves using per-square diffs (from+to)
        best_score = -1.0
        best_move = None
        # Robust, percentile-based floor
        p90 = float(np.percentile(diffs, 90))
        p95 = float(np.percentile(diffs, 95))
        med = float(np.median(diffs))
        sd = float(np.std(diffs))
        threshold = max(p95 * 1.15, p90 * 1.35, med + 3 * sd, med * 6.0, 10.0)
        for mv in self.board.legal_moves:
            r_from, c_from = self._square_to_index(mv.from_square)
            r_to, c_to = self._square_to_index(mv.to_square)
            score = diffs[r_from, c_from] + diffs[r_to, c_to]
            if score > best_score:
                best_score = score
                best_move = mv
        # Require score to be significantly above background
        if self.debug:
            # Log top-5 move scores
            scored = []
            for mv in self.board.legal_moves:
                r_from, c_from = self._square_to_index(mv.from_square)
                r_to, c_to = self._square_to_index(mv.to_square)
                score = diffs[r_from, c_from] + diffs[r_to, c_to]
                scored.append((score, mv.uci()))
            scored.sort(reverse=True)
            with open(os.path.join('boards', 'debug', 'scores.log'), 'a', encoding='utf-8') as f:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n[{ts}] top scores (threshold={threshold:.2f}): {scored[:5]}\n")
        if best_score > threshold:
            return best_move
        return None

    def monitor_opponent_move(self):
        print("Monitoring for opponent's move...")
        if self.previous_screenshot is None:
            prev_img, prev_path = self.capture_board_screenshot(save=True, label="baseline")
            self.previous_screenshot = prev_img
            self.previous_screenshot_path = prev_path
        noise_strikes = 0
        while True:
            time.sleep(5)
            curr_img, curr_path = self.capture_board_screenshot(save=True, label="poll")
            # Quick identical check
            if self._images_similar(self.previous_screenshot, curr_img):
                if curr_path and os.path.exists(curr_path):
                    if self.debug:
                        shutil.copy(curr_path, os.path.join('boards', 'debug', os.path.basename(curr_path)))
                    try:
                        os.remove(curr_path)
                    except OSError:
                        pass
                print("Poll unchanged -> deleted latest; keep baseline.")
                continue
            # Try to decode a legal move
            mv = self.detect_opponent_move(self.previous_screenshot, curr_img)
            if mv is None:
                # Likely animation/UI noise. Delete latest and try again a few times.
                noise_strikes += 1
                if curr_path and os.path.exists(curr_path):
                    if self.debug:
                        shutil.copy(curr_path, os.path.join('boards', 'debug', os.path.basename(curr_path)))
                    try:
                        os.remove(curr_path)
                    except OSError:
                        pass
                print(f"Poll changed but no legal move decoded (#{noise_strikes}). Keeping baseline.")
                # After several strikes, refresh baseline to avoid being stuck on highlights
                if noise_strikes >= 3:
                    if self.previous_screenshot_path and os.path.exists(self.previous_screenshot_path):
                        try:
                            os.remove(self.previous_screenshot_path)
                        except OSError:
                            pass
                    self.previous_screenshot = curr_img
                    self.previous_screenshot_path = curr_path
                    noise_strikes = 0
                    print("Baseline refreshed due to persistent UI changes.")
                continue
            # Valid move detected
            if self.previous_screenshot_path and os.path.exists(self.previous_screenshot_path):
                if self.debug:
                    shutil.copy(self.previous_screenshot_path, os.path.join('boards', 'debug', os.path.basename(self.previous_screenshot_path)))
                try:
                    os.remove(self.previous_screenshot_path)
                except OSError:
                    pass
            print(f"Detected opponent move: {mv.uci()}")
            self.previous_screenshot = curr_img
            self.previous_screenshot_path = curr_path
            return mv

    # ---- Main loop ----
    def play_game(self):
        # Orientation
        self.detect_player_color()
        if not self.playing_white:
            print("Detected Black orientation. White-only flow is implemented for now.")
            return
        # Baseline before any move
        prev_img, prev_path = self.capture_board_screenshot(save=True, label="before_first_move")
        self.previous_screenshot = prev_img
        self.previous_screenshot_path = prev_path
        print("Playing as White - making first move")
        self.make_white_move()
        
        while not self.board.is_game_over():
            print("Waiting for opponent's move...")
            opp = self.monitor_opponent_move()
            if opp is None:
                continue
            # Update internal board with opponent move
            self.board.push(opp)
            # Our reply
            self.make_white_move()
        
        print("Game over!")
        print(f"Result: {self.board.result()}")

    def close(self):
        self.engine.quit()


if __name__ == "__main__":
    STOCKFISH_PATH = os.getenv('STOCKFISH_PATH', 'stockfish.exe')
    depth_env = os.getenv('CHESSTER_DEPTH')
    depth = int(depth_env) if depth_env else 15
    bot = ChessBot(STOCKFISH_PATH, search_depth=depth)
    try:
        bot.play_game()
    finally:
        bot.close()
