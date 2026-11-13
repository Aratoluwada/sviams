"""Role A: plate image -> plate text, using the team's trained LPRNet model. Not built yet.

Contract (guide section 2.3):
  read_plate(image) -> plate text such as "ABC123XY", or None if the read is not confident.

Notes for the build:
  - The model comes from the model trainer. It replaces the earlier Tesseract plan.
  - The model reads a cropped plate. Agree with the trainer how the crop is made
    (a guide box on the live preview, or a plate detector).
  - Preprocess the crop exactly as in training (the model input is 192x48).
  - Run on the Pi CPU. Prefer an exported ONNX model with ONNX Runtime and a NumPy
    decoder, so PyTorch is not needed on the Pi.
  - Return None when confidence is low, so logic.py reports NO PLATE and the operator
    retries. Never return a confident guess for a plate that does not fit the pattern.
  - Measure exact-match accuracy on saved plate photos before using the live camera.
"""
