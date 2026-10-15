# Arcade Snake Game 🐍

A retro arcade Snake game built with Python and Pygame.

## Features

- **Smooth Arcade Controls**: Responsive controls with an input buffer to prevent accidental self-collisions when turning rapidly.
- **Directional Snake Eyes**: The snake's eyes dynamically gaze in the direction it is moving.
- **Particle Effects**: Particle bursts when eating food and on collision.
- **Apples & Bonus Gold**: Standard apples (+10 pts) and timed golden bonus apples (up to +50 pts) that spawn periodically.
- **Dynamic Speed Scaling**: Game speed ramps up smoothly as you grow.
- **8-Bit Procedural Audio**: Built-in chimes and sound effects with zero external audio assets required (press `M` to mute anytime).
- **Persistent High Scores**: Automatically saves and loads your best score.

---

## Quick Start

Run the game directly with the virtual environment:

```bash
.venv/bin/python snake.py
```

Or using `python3` (with `pygame` installed):

```bash
python3 snake.py
```

---

## Controls

| Key | Action |
| :--- | :--- |
| `↑` / `W` | Move Up |
| `↓` / `S` | Move Down |
| `←` / `A` | Move Left |
| `→` / `D` | Move Right |
| `Space` / `P` | Pause / Resume |
| `M` | Mute / Unmute Sound |
| `Enter` / `R` | Restart after Game Over |
| `Esc` / `Q` | Quit Game |
