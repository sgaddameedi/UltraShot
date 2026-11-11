# Contributing to UltraShot

Thank you for your interest in the project. UltraShot exists because sharing HDR game screenshots is
still considerably harder than it ought to be, and every bug report, every test on an unfamiliar game
or phone, and every pull request makes that a little less true. This document explains how to set up a
development environment, how the code is organised, and what a good contribution looks like.

## Ways to contribute

The most valuable reports are the ones that describe what you saw in concrete terms: which game, which
capture tool, which application and device displayed the result, and what went wrong. HDR behaviour
varies enormously between viewers, and a short note that a post looks dim in Threads on a particular
phone, with the capture attached, can save hours of guesswork.

Testing with sources the project has not verified is equally useful. Captures from Special K, from
other overlays, or from consoles may decode differently, and knowing how they behave extends the
supported-sources table for everyone.

Documentation improvements are always welcome. If a guide was unclear to you, it will be unclear to
others, and a pull request that fixes the wording is as valuable as one that fixes code.

Code contributions are discussed below, with a list of ideas at the end.

## Setting up a development environment

UltraShot requires Windows 10 or 11, because the interface runs in the Edge WebView2 runtime that
ships with Windows, and Python 3.11 or later.

```bash
git clone https://github.com/sgaddameedi/UltraShot.git
cd UltraShot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python ultrashot.py --new-instance
```

The `--new-instance` flag matters if an installed copy of UltraShot is already running in the tray.
Without it, a development copy simply hands its arguments to the running instance and exits, which is
the correct behaviour for users and a confusing one for developers.

Other commands you will use regularly:

```bash
pytest                                                 # engine tests; no display or sample files needed
python jxl2uhdr.py input.jxl output.jpg --max-width 1440   # the engine as a command-line tool
python tools\screenshots.py                            # regenerates docs\screenshots from the real UI
build_exe.bat                                          # builds dist\UltraShot\UltraShot.exe
```

## How the code is organised

| Path | Purpose |
| --- | --- |
| `jxl2uhdr.py` | The conversion engine. It decodes JPEG XL and JPEG XR files to linear nits, renders the SDR base image, and encodes the Ultra HDR JPEG through imagecodecs and libultrahdr. It is pure Python and NumPy with no knowledge of the application. |
| `ultrashot.py` | The desktop application: the file registry, preview cache, conversion queue, watch folder, settings, tray icon, single-instance server, Explorer and Startup integration, and the `Api` class whose methods the page calls. |
| `ui/` | The front end, written in plain HTML, CSS and JavaScript with no build step. `app.js` calls Python through `pywebview.api` and receives events through `app.on(name, payload)`. |
| `tools/` | Developer utilities for screenshots, the logo, the sample files, and the console watcher. |
| `tests/` | The pytest suite for the engine. |
| `docs/` | The guides and the images used by the README. |

A few conventions keep the project coherent, and pull requests are reviewed against them.

The HDR layer is never altered. Nothing in the pipeline may change the scene-referred HDR data apart
from cropping and resizing. Exposure, the highlight knee and every other "look" control act on the SDR
base image alone. A feature that needs to change the HDR data is a feature that needs a discussion
first.

The engine stays free of GUI code and importable on its own. A new conversion capability belongs in
`jxl2uhdr.py` as a function parameter, and is exposed in the application afterwards.

The user interface stays as vanilla HTML, CSS and JavaScript. The absence of a build step is deliberate,
so that anyone can open `ui/` and make a change without installing a toolchain.

Settings are plain keys in `DEFAULTS` in `ultrashot.py` and rows in `SECTIONS` in `ui/app.js`. Adding a
setting is usually those two edits plus the code that reads it.

Style follows the existing code: four-space indentation and `snake_case` in Python, with docstrings on
anything non-obvious; two-space indentation in JavaScript.

## Submitting a pull request

For anything beyond a small fix, please open an issue first so that the approach can be agreed before
the work is done. Branch from `main`, keep the change focused on one thing, and describe in the pull
request what you tested and with what: the game, the capture tool and the viewer. Run `pytest` before
submitting, and if the change touches the interface, run `python tools\screenshots.py` to confirm that
every screen still renders. Add a line describing the change to `CHANGELOG.md` under an "Unreleased"
heading.

By contributing you agree that your contribution is licensed under the MIT License, like the rest of
the project.

## Ideas that would be welcome

An HDR preview inside the application would remove the need to check results in a browser; it requires
either a WebView2 surface in HDR mode or a native swap chain. AVIF and HDR PNG outputs would serve
platforms that prefer those formats. Reading OpenEXR and Radiance HDR files would extend the tool to
rendered images as well as game captures. Ports of the application shell to macOS and Linux are
feasible, since the engine already runs wherever imagecodecs does. Localisation of the interface is
straightforward given the small amount of text involved.
