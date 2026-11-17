# test

**Owner:** David (testing)

Accuracy (character error rate) and timing scripts. Run `pytest` from the repo root.

| File | Covers |
|---|---|
| `test_dotmap.py` | Pico dot-to-bit mapping and 74HC595 chain order. |
| `test_jetson_units.py` | Braille translation, paging, reader state machine, serial frame, error-rate metric. |
| `test_jetson_pipeline.py` | Page finding, rectification, lighting correction and end-to-end OCR on a synthetic page. Skipped if Tesseract or a TrueType font is missing. |
| `synth.py` | Makes the synthetic pages. |
| `ocr_accuracy.py` | Script, not a test: character error rate and time per page for a folder of real photos, or for synthetic pages. |
| `test_placeholder.py` | Setup check from the first commit. |

Synthetic pages check the software only. The spec numbers (over 95% accuracy, under 5 s) must be measured on the rig with `ocr_accuracy.py`.
