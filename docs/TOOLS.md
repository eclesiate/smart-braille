# Tools (dev machine: macOS 15.7.7, arm64, Homebrew)

| Tool | Version | Notes |
|---|---|---|
| git | 2.39.5 (Apple) | |
| Python | 3.13.14 (Homebrew) | venv at `.venv`, created with `/opt/homebrew/bin/python3.13` |
| pytest | 9.2.0 | in `.venv` |
| numpy | 2.5.5 | in `.venv` |
| opencv-python | 5.0.0.93 | in `.venv` |
| pyserial | 3.5 | in `.venv` |
| mpremote | 1.29.0 | in `.venv` |
| pytesseract | 0.3.13 | in `.venv`, wraps the brew tesseract binary |
| tesseract | 5.5.4 | `brew install tesseract` (eng + osd only) |
| liblouis | 3.39.0 | `brew install liblouis`. Python bindings (`louis`) come from the brew package, exposed to `.venv` through a `.pth` file pointing at `/opt/homebrew/Cellar/liblouis/3.39.0/lib/python3.15/site-packages`. If `brew upgrade liblouis` changes the version, update that path. Tables: `/opt/homebrew/share/liblouis/tables` (use `unicode.dis` + `en-ueb-g1.ctb` for uncontracted UEB). |
| gh | already installed | logged in |
| KiCad | 10.0.8 | `brew install --cask kicad`, full app in `/Applications/KiCad/`. `kicad-cli` symlinked: `ln -s /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli /opt/homebrew/bin/kicad-cli` |

The Pico runs MicroPython. Firmware images are flashed manually, not downloaded by tooling.

Real tesseract/liblouis versions run on the Jetson; the ones here are for local testing only.
