#!/usr/bin/env python3
"""
Arcade Snake Game in Python with Pygame
---------------------------------------
Features:
  - Smooth 60 FPS rendering with input buffer (no rapid-key self-collisions)
  - Expressive animated snake with eyes tracking movement direction
  - Particle burst effects on eating food
  - Regular apples and timed golden bonus apples
  - Procedural 8-bit sound effects (with Mute toggle)
  - Persistent High Score tracking (.snake_highscore.json)
  - Pause / Resume, Game Over screens, and progressive speed scaling
  - Arrow keys + WASD support
"""

import sys
import os
import math
import array
import random
import json
from collections import deque
import pygame

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
CELL_SIZE = 25
GRID_COLS = 32
GRID_ROWS = 22

BOARD_WIDTH = GRID_COLS * CELL_SIZE   # 800
BOARD_HEIGHT = GRID_ROWS * CELL_SIZE # 550
HUD_HEIGHT = 50

SCREEN_WIDTH = BOARD_WIDTH             # 800
SCREEN_HEIGHT = BOARD_HEIGHT + HUD_HEIGHT # 600

FPS = 60
BASE_TICK_RATE = 9.0     # Initial moves per second
MAX_TICK_RATE = 22.0    # Maximum moves per second
SPEED_INCREMENT = 0.45  # Moves/sec added per regular food

HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".snake_highscore.json")

# Colors (Modern Arcade Palette)
COLOR_BG_DARK = (16, 18, 24)
COLOR_BG_LIGHT = (22, 25, 34)
COLOR_GRID_LINE = (28, 32, 44)
COLOR_HUD_BG = (12, 14, 19)
COLOR_TEXT_PRIMARY = (240, 243, 246)
COLOR_TEXT_MUTED = (140, 148, 160)
COLOR_ACCENT = (255, 204, 0)

COLOR_SNAKE_HEAD = (46, 204, 113)
COLOR_SNAKE_BODY_1 = (39, 174, 96)
COLOR_SNAKE_BODY_2 = (34, 153, 84)
COLOR_SNAKE_EYE = (255, 255, 255)
COLOR_SNAKE_PUPIL = (20, 25, 30)

COLOR_FOOD_APPLE = (231, 76, 60)
COLOR_FOOD_STEM = (139, 69, 19)
COLOR_FOOD_LEAF = (46, 204, 113)
COLOR_BONUS_GOLD = (241, 196, 15)
COLOR_BONUS_OUTLINE = (255, 235, 120)

# Directions
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)

OPPOSITES = {
    DIR_UP: DIR_DOWN,
    DIR_DOWN: DIR_UP,
    DIR_LEFT: DIR_RIGHT,
    DIR_RIGHT: DIR_LEFT,
}


# -----------------------------------------------------------------------------
# Sound Synthesizer (Zero external audio assets required)
# -----------------------------------------------------------------------------
class SoundManager:
    """Generates procedural 8-bit sound effects using pygame mixer."""
    def __init__(self):
        self.enabled = False
        self.muted = False
        self.eat_sound = None
        self.bonus_sound = None
        self.die_sound = None

        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.enabled = True
            self.eat_sound = self._synth_tone(start_f=350, end_f=700, duration_ms=110, volume=0.35)
            self.bonus_sound = self._synth_arp([523, 659, 784, 1046], duration_per_tone_ms=45, volume=0.4)
            self.die_sound = self._synth_noise_buzz(duration_ms=400, volume=0.45)
        except Exception:
            # Audio device unavailable or restricted; fail gracefully to silent mode
            self.enabled = False

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    def play_eat(self):
        if self.enabled and not self.muted and self.eat_sound:
            self.eat_sound.play()

    def play_bonus(self):
        if self.enabled and not self.muted and self.bonus_sound:
            self.bonus_sound.play()

    def play_die(self):
        if self.enabled and not self.muted and self.die_sound:
            self.die_sound.play()

    def _synth_tone(self, start_f, end_f, duration_ms, volume=0.3):
        sample_rate = 22050
        n_samples = int(sample_rate * duration_ms / 1000)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / sample_rate
            progress = i / max(1, n_samples)
            freq = start_f + (end_f - start_f) * progress
            # Sine wave with simple linear decay envelope
            amp = volume * (1.0 - progress * 0.8)
            val = int(32767 * amp * math.sin(2 * math.pi * freq * t))
            buf.append(val)
        return pygame.mixer.Sound(buffer=buf)

    def _synth_arp(self, freqs, duration_per_tone_ms, volume=0.3):
        sample_rate = 22050
        buf = array.array('h')
        for freq in freqs:
            n_samples = int(sample_rate * duration_per_tone_ms / 1000)
            for i in range(n_samples):
                t = i / sample_rate
                decay = 1.0 - (i / max(1, n_samples)) * 0.5
                val = int(32767 * volume * decay * math.sin(2 * math.pi * freq * t))
                buf.append(val)
        return pygame.mixer.Sound(buffer=buf)

    def _synth_noise_buzz(self, duration_ms, volume=0.4):
        sample_rate = 22050
        n_samples = int(sample_rate * duration_ms / 1000)
        buf = array.array('h')
        for i in range(n_samples):
            progress = i / max(1, n_samples)
            # Low pitch slide with slight square clipping
            freq = 200 - 150 * progress
            t = i / sample_rate
            sin_val = math.sin(2 * math.pi * freq * t)
            clipped = 1.0 if sin_val > 0 else -1.0
            mixed = (sin_val * 0.4 + clipped * 0.6) * (1.0 - progress) * volume
            buf.append(int(32767 * mixed))
        return pygame.mixer.Sound(buffer=buf)


# -----------------------------------------------------------------------------
# Particle System
# -----------------------------------------------------------------------------
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 4.5)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.size = random.uniform(3, 5.5)
        self.life = 1.0
        self.decay = random.uniform(0.025, 0.055)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.08  # subtle gravity
        self.life -= self.decay
        self.size = max(0, self.size - 0.05)

    def draw(self, surface):
        if self.life > 0 and self.size > 0.5:
            alpha = max(0, min(255, int(self.life * 255)))
            temp_surf = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
            color_with_alpha = (*self.color, alpha)
            pygame.draw.circle(temp_surf, color_with_alpha, (int(self.size), int(self.size)), int(self.size))
            surface.blit(temp_surf, (self.x - self.size, self.y - self.size))


# -----------------------------------------------------------------------------
# Main Game Class
# -----------------------------------------------------------------------------
class SnakeGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Arcade Snake")

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_large = pygame.font.SysFont("Helvetica", 48, bold=True)
        self.font_mid = pygame.font.SysFont("Helvetica", 24, bold=True)
        self.font_small = pygame.font.SysFont("Helvetica", 16)
        self.font_hud = pygame.font.SysFont("Helvetica", 20, bold=True)

        self.sounds = SoundManager()
        self.high_score = self.load_high_score()
        self.is_new_high_score = False

        self.state = "START"  # "START", "PLAYING", "PAUSED", "GAME_OVER"
        self.reset_game()

    def load_high_score(self) -> int:
        if os.path.exists(HIGHSCORE_FILE):
            try:
                with open(HIGHSCORE_FILE, "r") as f:
                    data = json.load(f)
                    return int(data.get("high_score", 0))
            except Exception:
                return 0
        return 0

    def save_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                json.dump({"high_score": self.high_score}, f)
        except Exception:
            pass

    def reset_game(self):
        # Initial Snake in center of board
        start_x = GRID_COLS // 2
        start_y = GRID_ROWS // 2
        self.snake = [
            (start_x, start_y),
            (start_x - 1, start_y),
            (start_x - 2, start_y),
        ]
        self.direction = DIR_RIGHT
        self.input_queue = deque()

        self.score = 0
        self.apples_eaten = 0
        self.tick_rate = BASE_TICK_RATE
        self.move_timer = 0.0
        self.is_new_high_score = False

        self.particles = []

        # Food & bonus food
        self.bonus_food = None
        self.bonus_timer = 0.0
        self.bonus_duration = 7.0  # seconds bonus stays active
        self.food = self.spawn_food()

    def spawn_food(self):
        occupied = set(self.snake)
        if self.bonus_food:
            occupied.add((self.bonus_food[0], self.bonus_food[1]))

        free_cells = [
            (col, row)
            for col in range(GRID_COLS)
            for row in range(GRID_ROWS)
            if (col, row) not in occupied
        ]
        if not free_cells:
            return (0, 0)
        return random.choice(free_cells)

    def spawn_bonus_food(self):
        occupied = set(self.snake)
        occupied.add(self.food)
        free_cells = [
            (col, row)
            for col in range(GRID_COLS)
            for row in range(GRID_ROWS)
            if (col, row) not in occupied
        ]
        if free_cells:
            cell = random.choice(free_cells)
            self.bonus_food = cell
            self.bonus_timer = self.bonus_duration

    def add_explosion(self, grid_col, grid_row, color, count=16):
        cx = grid_col * CELL_SIZE + CELL_SIZE // 2
        cy = HUD_HEIGHT + grid_row * CELL_SIZE + CELL_SIZE // 2
        for _ in range(count):
            self.particles.append(Particle(cx, cy, color))

    # -------------------------------------------------------------------------
    # Input Handling
    # -------------------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                # Global sound mute toggle
                if event.key == pygame.K_m:
                    self.sounds.toggle_mute()

                # Start screen
                if self.state == "START":
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.state = "PLAYING"

                # Playing
                elif self.state == "PLAYING":
                    if event.key in (pygame.K_p, pygame.K_SPACE):
                        self.state = "PAUSED"
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "PAUSED"
                    else:
                        self.enqueue_direction(event.key)

                # Paused
                elif self.state == "PAUSED":
                    if event.key in (pygame.K_p, pygame.K_SPACE, pygame.K_ESCAPE):
                        self.state = "PLAYING"

                # Game Over
                elif self.state == "GAME_OVER":
                    if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                        self.reset_game()
                        self.state = "PLAYING"
                    elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                        pygame.quit()
                        sys.exit()

    def enqueue_direction(self, key):
        new_dir = None
        if key in (pygame.K_UP, pygame.K_w):
            new_dir = DIR_UP
        elif key in (pygame.K_DOWN, pygame.K_s):
            new_dir = DIR_DOWN
        elif key in (pygame.K_LEFT, pygame.K_a):
            new_dir = DIR_LEFT
        elif key in (pygame.K_RIGHT, pygame.K_d):
            new_dir = DIR_RIGHT

        if new_dir is not None and len(self.input_queue) < 3:
            # Check against either current direction or the last queued direction
            reference_dir = self.input_queue[-1] if self.input_queue else self.direction
            if new_dir != reference_dir and new_dir != OPPOSITES[reference_dir]:
                self.input_queue.append(new_dir)

    # -------------------------------------------------------------------------
    # Game Logic & Updates
    # -------------------------------------------------------------------------
    def update(self, dt):
        # Update particles regardless of state
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        if self.state != "PLAYING":
            return

        # Bonus timer countdown
        if self.bonus_food:
            self.bonus_timer -= dt
            if self.bonus_timer <= 0:
                self.bonus_food = None

        # Movement accumulator
        self.move_timer += dt
        move_delay = 1.0 / self.tick_rate

        while self.move_timer >= move_delay:
            self.move_timer -= move_delay
            self.step_snake()
            if self.state != "PLAYING":
                break

    def step_snake(self):
        # Apply next buffered direction if available
        if self.input_queue:
            next_dir = self.input_queue.popleft()
            if next_dir != OPPOSITES[self.direction]:
                self.direction = next_dir

        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # 1. Wall Collision
        if (
            new_head[0] < 0
            or new_head[0] >= GRID_COLS
            or new_head[1] < 0
            or new_head[1] >= GRID_ROWS
        ):
            self.trigger_game_over()
            return

        # 2. Self Collision
        # Note: tail will move away unless we are eating this tick
        will_eat = (new_head == self.food) or (self.bonus_food and new_head == self.bonus_food)
        body_to_check = self.snake if will_eat else self.snake[:-1]
        if new_head in body_to_check:
            self.trigger_game_over()
            return

        # Move forward
        self.snake.insert(0, new_head)

        # 3. Eat Regular Food
        if new_head == self.food:
            self.score += 10
            self.apples_eaten += 1
            self.sounds.play_eat()
            self.add_explosion(new_head[0], new_head[1], COLOR_FOOD_APPLE, count=18)

            # Progressive speed up
            self.tick_rate = min(MAX_TICK_RATE, BASE_TICK_RATE + self.apples_eaten * SPEED_INCREMENT)

            # Spawn bonus apple every 5 regular apples
            if self.apples_eaten % 5 == 0 and not self.bonus_food:
                self.spawn_bonus_food()

            self.food = self.spawn_food()

        # 4. Eat Bonus Food
        elif self.bonus_food and new_head == self.bonus_food:
            bonus_points = max(20, int(50 * (self.bonus_timer / self.bonus_duration)))
            self.score += bonus_points
            self.sounds.play_bonus()
            self.add_explosion(new_head[0], new_head[1], COLOR_BONUS_GOLD, count=28)
            self.bonus_food = None

        else:
            # Normal move, remove tail
            self.snake.pop()

        # Check high score
        if self.score > self.high_score:
            self.high_score = self.score
            self.is_new_high_score = True
            self.save_high_score()

    def trigger_game_over(self):
        self.sounds.play_die()
        head_x, head_y = self.snake[0]
        self.add_explosion(head_x, head_y, (231, 76, 60), count=35)
        self.state = "GAME_OVER"

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------
    def draw(self):
        # 1. Background
        self.screen.fill(COLOR_BG_DARK)

        # Subtle checkerboard on the board
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS):
                if (col + row) % 2 == 1:
                    rect = pygame.Rect(
                        col * CELL_SIZE,
                        HUD_HEIGHT + row * CELL_SIZE,
                        CELL_SIZE,
                        CELL_SIZE,
                    )
                    pygame.draw.rect(self.screen, COLOR_BG_LIGHT, rect)

        # 2. Draw Food
        self.draw_food()

        # 3. Draw Bonus Food
        if self.bonus_food:
            self.draw_bonus_food()

        # 4. Draw Snake
        self.draw_snake()

        # 5. Draw Particles
        for p in self.particles:
            p.draw(self.screen)

        # 6. HUD (Top Bar)
        self.draw_hud()

        # 7. Overlays for Start / Pause / Game Over
        if self.state == "START":
            self.draw_start_screen()
        elif self.state == "PAUSED":
            self.draw_paused_overlay()
        elif self.state == "GAME_OVER":
            self.draw_game_over_screen()

        pygame.display.flip()

    def draw_hud(self):
        # Header background
        hud_rect = pygame.Rect(0, 0, SCREEN_WIDTH, HUD_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_HUD_BG, hud_rect)
        pygame.draw.line(self.screen, (40, 46, 62), (0, HUD_HEIGHT - 1), (SCREEN_WIDTH, HUD_HEIGHT - 1), 2)

        # Score
        score_surf = self.font_hud.render(f"SCORE: {self.score:04d}", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(score_surf, (20, (HUD_HEIGHT - score_surf.get_height()) // 2))

        # High Score
        hs_color = COLOR_ACCENT if self.is_new_high_score else COLOR_TEXT_MUTED
        hs_surf = self.font_hud.render(f"BEST: {self.high_score:04d}", True, hs_color)
        self.screen.blit(hs_surf, (220, (HUD_HEIGHT - hs_surf.get_height()) // 2))

        # Speed level
        speed_level = int(1 + (self.tick_rate - BASE_TICK_RATE) / SPEED_INCREMENT)
        speed_surf = self.font_small.render(f"SPEED: LVL {speed_level}", True, COLOR_TEXT_MUTED)
        self.screen.blit(speed_surf, (430, (HUD_HEIGHT - speed_surf.get_height()) // 2))

        # Mute indicator & Controls tip
        mute_text = "MUTED [M]" if self.sounds.muted else "SOUND [M]"
        mute_surf = self.font_small.render(mute_text, True, COLOR_TEXT_MUTED)
        self.screen.blit(mute_surf, (SCREEN_WIDTH - 110, (HUD_HEIGHT - mute_surf.get_height()) // 2))

    def draw_food(self):
        col, row = self.food
        cx = col * CELL_SIZE + CELL_SIZE // 2
        cy = HUD_HEIGHT + row * CELL_SIZE + CELL_SIZE // 2
        radius = CELL_SIZE // 2 - 2

        # Apple body
        pygame.draw.circle(self.screen, COLOR_FOOD_APPLE, (cx, cy + 1), radius)
        # Highlight
        pygame.draw.circle(self.screen, (255, 120, 110), (cx - 2, cy - 2), max(2, radius // 3))
        # Small green leaf & stem
        pygame.draw.line(self.screen, COLOR_FOOD_STEM, (cx, cy - radius), (cx + 2, cy - radius - 3), 2)
        pygame.draw.circle(self.screen, COLOR_FOOD_LEAF, (cx + 4, cy - radius - 2), 2)

    def draw_bonus_food(self):
        col, row = self.bonus_food
        cx = col * CELL_SIZE + CELL_SIZE // 2
        cy = HUD_HEIGHT + row * CELL_SIZE + CELL_SIZE // 2

        # Pulsing golden orb effect
        pulse = 1.0 + 0.15 * math.sin(pygame.time.get_ticks() * 0.01)
        radius = int((CELL_SIZE // 2 - 1) * pulse)

        pygame.draw.circle(self.screen, COLOR_BONUS_GOLD, (cx, cy), radius)
        pygame.draw.circle(self.screen, COLOR_BONUS_OUTLINE, (cx, cy), radius, 2)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx - 2, cy - 2), max(2, radius // 3))

        # Remaining time mini-ring
        time_ratio = max(0.0, self.bonus_timer / self.bonus_duration)
        if time_ratio > 0:
            bar_w = int(CELL_SIZE * time_ratio)
            bar_y = HUD_HEIGHT + (row + 1) * CELL_SIZE - 4
            pygame.draw.rect(self.screen, COLOR_BONUS_GOLD, (col * CELL_SIZE, bar_y, bar_w, 3))

    def draw_snake(self):
        for idx, (col, row) in enumerate(self.snake):
            x = col * CELL_SIZE
            y = HUD_HEIGHT + row * CELL_SIZE
            rect = pygame.Rect(x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2)

            if idx == 0:
                # Head: Rounded rectangle
                pygame.draw.rect(self.screen, COLOR_SNAKE_HEAD, rect, border_radius=8)
                self.draw_snake_eyes(col, row)
            else:
                # Body: Alternating shaded rounded segments
                body_color = COLOR_SNAKE_BODY_1 if idx % 2 == 0 else COLOR_SNAKE_BODY_2
                border_rad = 5 if idx < len(self.snake) - 1 else 8
                pygame.draw.rect(self.screen, body_color, rect, border_radius=border_rad)

    def draw_snake_eyes(self, head_col, head_row):
        """Draws cute directional eyes on the snake's head."""
        cx = head_col * CELL_SIZE + CELL_SIZE // 2
        cy = HUD_HEIGHT + head_row * CELL_SIZE + CELL_SIZE // 2
        dx, dy = self.direction

        eye_radius = 3.5
        pupil_radius = 1.8

        # Eye offsets perpendicular to moving direction
        if dx != 0:  # Moving horizontally
            eye_offsets = [(dx * 4, -5), (dx * 4, 5)]
        else:        # Moving vertically
            eye_offsets = [(-5, dy * 4), (5, dy * 4)]

        for ox, oy in eye_offsets:
            ex = cx + ox
            ey = cy + oy
            # White sclera
            pygame.draw.circle(self.screen, COLOR_SNAKE_EYE, (int(ex), int(ey)), int(eye_radius))
            # Dark pupil gazing toward movement direction
            px = ex + dx * 1.5
            py = ey + dy * 1.5
            pygame.draw.circle(self.screen, COLOR_SNAKE_PUPIL, (int(px), int(py)), int(pupil_radius))

    # -------------------------------------------------------------------------
    # Screen Overlays
    # -------------------------------------------------------------------------
    def _draw_dim_backdrop(self, alpha=180):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 12, 16, alpha))
        self.screen.blit(overlay, (0, 0))

    def draw_start_screen(self):
        self._draw_dim_backdrop(210)

        title = self.font_large.render("ARCADE SNAKE", True, COLOR_SNAKE_HEAD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 100))
        self.screen.blit(title, title_rect)

        prompt = self.font_mid.render("Press SPACE or ENTER to Start", True, COLOR_ACCENT)
        prompt_rect = prompt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
        self.screen.blit(prompt, prompt_rect)

        ctrl1 = self.font_small.render("Controls: Arrow Keys or W / A / S / D", True, COLOR_TEXT_PRIMARY)
        ctrl2 = self.font_small.render("P / Space: Pause   |   M: Mute Sound   |   Esc: Quit", True, COLOR_TEXT_MUTED)
        self.screen.blit(ctrl1, ctrl1.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)))
        self.screen.blit(ctrl2, ctrl2.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 80)))

        if self.high_score > 0:
            hs = self.font_hud.render(f"Current High Score: {self.high_score}", True, COLOR_ACCENT)
            self.screen.blit(hs, hs.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 130)))

    def draw_paused_overlay(self):
        self._draw_dim_backdrop(160)

        text = self.font_large.render("PAUSED", True, COLOR_TEXT_PRIMARY)
        text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        self.screen.blit(text, text_rect)

        sub = self.font_mid.render("Press SPACE or P to Resume", True, COLOR_ACCENT)
        sub_rect = sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 25))
        self.screen.blit(sub, sub_rect)

    def draw_game_over_screen(self):
        self._draw_dim_backdrop(220)

        title = self.font_large.render("GAME OVER", True, (231, 76, 60))
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 110))
        self.screen.blit(title, title_rect)

        score_text = self.font_mid.render(f"Final Score: {self.score}", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(score_text, score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 45)))

        if self.is_new_high_score:
            hs_msg = self.font_mid.render("★ NEW HIGH SCORE! ★", True, COLOR_ACCENT)
            self.screen.blit(hs_msg, hs_msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10)))
        else:
            hs_msg = self.font_hud.render(f"High Score: {self.high_score}", True, COLOR_TEXT_MUTED)
            self.screen.blit(hs_msg, hs_msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10)))

        restart_text = self.font_mid.render("Press ENTER or R to Play Again", True, COLOR_SNAKE_HEAD)
        self.screen.blit(restart_text, restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 55)))

        quit_text = self.font_small.render("Press Q or ESC to Quit", True, COLOR_TEXT_MUTED)
        self.screen.blit(quit_text, quit_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 95)))

    # -------------------------------------------------------------------------
    # Main Loop
    # -------------------------------------------------------------------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            self.handle_events()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    game = SnakeGame()
    game.run()
