"""Role A: camera preview and still capture (Picamera2). Not built yet.

Contract (guide section 2.3):
  stream_frames()  -> generator of JPEG frames for /video_feed (low resolution)
  capture_still()  -> an image object or file path for anpr.read_plate()
  On failure, raise an exception. Never return a half-made image.
"""


def stream_frames():
    raise NotImplementedError


def capture_still():
    raise NotImplementedError
