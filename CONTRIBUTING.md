# Contributing to UltraShot

Thanks for your interest. UltraShot exists because sharing HDR game screenshots is still far harder
than it should be, and every report, test on a new game or phone, and pull request moves that along.

## Ways to help

- **Report what you see.** Which game, which capture tool, which phone or app displayed it, and what
  went wrong. HDR behaviour differs wildly across apps, and a short "Threads on a Pixel 9 shows it
  dim" report is valuable.
- **Test formats and sources.** Bring captures from tools we have not verified (Special K, other
  overlays, consoles) and tell us how they decode.
- **Improve the docs.** If a guide confused you, it will confuse others.
- **Code.** See the ideas list at the end.

## Development setup

Requirements: Windows 10/11 (the UI runs in Edge WebView2, which ships with Windows), Python 3.11+.

```bash
git clone https://github.com/sgaddameedi/UltraShot.git
cd UltraShot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python ultrashot.py --new-instance
```

`--new-instance` lets a development copy run next to an installed UltraShot that is already sitting
in the tray; without it the dev copy just hands over to the running one and exits.

Other useful commands:

```bash
pytest                      # encoder tests, no GUI needed
python jxl2uhdr.py in.jxl out.jpg --max-width 1440   # the engine as a command-line tool
python tools\screenshots.py # regenerates docs\screenshots\*.png from the real UI
build_exe.bat               # builds dist\UltraShot\UltraShot.exe
```

## Code layout

| Path | What it is |
| --- | --- |
| `jxl2uhdr.py` | The engine. Decodes JXL / JXR to linear nits, tone-maps the SDR base, encodes the Ultra HDR JPEG through `imagecodecs` / libultrahdr. Pure Python + NumPy, no GUI code. |
| `ultrashot.py` | The desktop app: file registry, preview cache, conversion queue, watch folder, settings, tray, single instance, Explorer / Startup integration, and the `Api` class the page calls. |
| `ui/` | The front end. Plain HTML, CSS and JavaScript, no build step. `app.js` talks to Python through `pywebview.api` and receives events through `app.on(name, payload)`. |
| `tools/` | Developer helpers: screenshots, logo and sample generation, the console watcher. |
| `tests/` | pytest suite for the engine. |
| `docs/` | Guides and images used by the README. |

Guidelines that keep the project coherent:

- The HDR layer is sacred. Nothing in the pipeline may alter the scene-referred HDR data except
  resizing and cropping. Exposure, knee and every "look" control affect the SDR base image only.
- The engine stays GUI-free and importable. If you add a conversion feature, add it to
  `jxl2uhdr.py` with a parameter and expose it in the app afterwards.
- No build step for the UI. Keep `ui/` to vanilla HTML/CSS/JS so anyone can edit it.
- Settings are plain keys in `DEFAULTS` (`ultrashot.py`) and rows in `SECTIONS` (`ui/app.js`).
  Adding a setting is usually those two edits plus the place that uses it.
- Match the existing style: 4-space Python, `snake_case`, type-light but documented; 2-space JS.

## Pull requests

1. Open an issue first for anything beyond a small fix, so the approach can be discussed.
2. Branch from `main`, keep the PR focused, and describe what you tested (game, capture tool,
   viewer).
3. Run `pytest` and, if you touched the UI, `python tools\screenshots.py` to make sure the screens
   still render.
4. Add a line to `CHANGELOG.md` under "Unreleased".

By contributing you agree that your contribution is licensed under the MIT License.

## Ideas that would be welcome

- HDR preview inside the app (needs a WebView2 surface in HDR mode or a native swap chain).
- AVIF (PQ) and HDR PNG outputs for platforms that prefer them.
- Reading OpenEXR / Radiance HDR renders.
- A macOS / Linux port of the GUI shell (the engine already runs anywhere `imagecodecs` does).
- Localisation of the UI.
