# BREWMETRIC POS

Coffee shop point-of-sale system — Python 3.8+, no dependencies. All pricing, cart, cup visualizer, prep queue and ingredient levels are rendered in Python. State is saved to `brewmetric_data.json`.

## Requirements

- Python 3.8+ (`python --version`)
- No `pip` dependencies

## How to Run

### Windows (PowerShell)

```powershell
cd "C:\Users\LEA\Python project"
python brewmetric.py        # -> http://localhost:8000
python brewmetric.py 8001   # custom port -> http://localhost:8001
# alternative filename (same code)
python index.py 8000
```

### macOS / Linux

```bash
cd "Python project"
python3 brewmetric.py        # -> http://localhost:8000
python3 brewmetric.py 8001
# or executable (shebang is LF at brewmetric.py:1)
chmod +x brewmetric.py
./brewmetric.py 8000
```

On start the server prints `BREWMETRIC POS running at http://localhost:<port>` and auto-opens your browser (`webbrowser.open` at `brewmetric.py:320`). Keep the terminal open; `Ctrl+C` to stop.

## Pages

- `/` — Home: size (`Small`/`Medium`/`Large`), toppings carousel, drink carousel, Cup Visualizer, Order Summary (`SEND TO PREP`)
- `/prep` — Preparation Screen: Active Orders Queue, ingredient gauges (`coffee`/`crema`/`chocolate`), Drink Specification
- `/brewmetric.css` — external stylesheet (`brewmetric.css:1`, served as `text/css` at `brewmetric.py:286`)

## Project Structure

```
brewmetric.py        # main app (start here)
index.py             # mirror of brewmetric.py for compatibility
brewmetric.css       # extracted from inline CSS (was brewmetric.py:137)
brewmetric_data.json # auto-created runtime state (gitignored)
```

## Notes

- State persists in `brewmetric_data.json` (`brewmetric.py:13`). Delete it to reset queue/levels.
- Port is `sys.argv[1]` at `brewmetric.py:317`; defaults to `8000`. If busy, use another port: `python brewmetric.py 8080`.
- Binds to `127.0.0.1` only.

## Push to GitHub

```bash
git init
git branch -M main
git remote add origin https://github.com/Lealene/BREWMATRICS.git
git add brewmetric.py brewmetric.css index.py .gitignore README.md
git commit -m "feat: initial BREWMETRIC POS"
git push -u origin main
```
