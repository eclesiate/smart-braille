"""Image sources. Which camera is installed is still an open question, so
the source is a parameter and nothing here assumes a particular camera."""

import cv2


class FileCamera:
    """Returns the same image file every time. For development and tests."""

    def __init__(self, path):
        self.path = str(path)

    def capture(self):
        image = cv2.imread(self.path, cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(self.path)
        return image


class OpenCVCamera:
    """Any source cv2.VideoCapture accepts: a device index or a pipeline string."""

    def __init__(self, source=0, width=None, height=None, warmup_frames=5):
        self.source = source
        self.width = width
        self.height = height
        self.warmup_frames = warmup_frames

    def capture(self):
        cap = cv2.VideoCapture(self.source)
        try:
            if not cap.isOpened():
                raise RuntimeError(f"cannot open camera {self.source!r}")
            if self.width:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            if self.height:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            # The first frames are taken before exposure and focus settle.
            for _ in range(self.warmup_frames):
                cap.read()
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("camera returned no frame")
            return frame
        finally:
            cap.release()
