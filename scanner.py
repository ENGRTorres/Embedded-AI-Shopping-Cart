import os
import subprocess
import numpy as np
from picamera2 import Picamera2
import time

class Scanner:
    """
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Produces scan events for the application.

    Prototype behavior (PC):
    - Simulate scanning by user input (typing/selecting a label).

    Future behavior (Raspberry Pi):
    - Capture frames from the Pi Camera and run an AI model to detect/identify items.

    Output format should be consistent across implementations, for example:
    - label (str)
    - confidence (float in [0, 1])
    - timestamp
    """

    def scan(self, raw_input: str):
        raise NotImplementedError


class FakeScanner(Scanner):
    """
    Fake scanner for development/testing.
    Treats the user's typed input as the scanned label.
    """
    def scan(self, raw_input: str):
        label = (raw_input or "").strip()
        if not label:
            return None, 0.0
        return label, 1.0


class EdgeImpulseCppScanner(Scanner):
    """
    Uses system Picamera2 for capture and a compiled C++ TFLite runner for inference.

    - Picamera2/libcamera works best with system Python on Raspberry Pi.
    - TFLite inference is done by a compiled C++ program (tflite_infer).
    - Python remains the "brain" (GUI + logic), C++ does the heavy lifting (inference).
    """

    def __init__(self, model_path: str, runner_path: str = "./tflite_infer", warmup_sec: float = 1.0):
        self.model_path = model_path
        self.runner_path = runner_path

        # These will hold the most recent AI result so the GUI can display it live
        self.last_label = None
        self.last_conf = 0.0

        # Start camera once at startup (much faster than starting/stopping every scan)
        self.picam2 = Picamera2()
        cfg = self.picam2.create_preview_configuration(main={"size": (640, 480)})
        self.picam2.configure(cfg)
        self.picam2.start()
        time.sleep(warmup_sec)

        # Input quantization:
        # - We used a "safe default" before.
        # - Now we will try to read the TRUE input quantization from the model
        #   by calling the C++ runner in a special mode.
        #
        # If the C++ runner query fails for any reason, we keep these fallback values.
        self.in_scale = 1.0 / 255.0
        self.in_zero = -128

        # Try to load real model quant params (best accuracy)
        self._load_quant_params_from_runner()

        self.temp_frame_path = "/tmp/frame.int8"

    def _load_quant_params_from_runner(self):
        """
        Ask the C++ runner to print the model's quantization parameters.
        Requires your C++ program to support:
            ./tflite_infer --print-quant model.tflite

        Expected output lines:
            INPUT <scale> <zero_point>
            OUTPUT <scale> <zero_point>

        We only use INPUT scale/zero_point here.
        """
        try:
            result = subprocess.run(
                [self.runner_path, "--print-quant", self.model_path],
                capture_output=True,
                text=True,
                check=False
            )

            # If the runner failed, just keep fallback values.
            if result.returncode != 0:
                return

            # Parse stdout line-by-line
            for line in result.stdout.strip().splitlines():
                parts = line.strip().split()
                if len(parts) != 3:
                    continue

                tag, scale_str, zero_str = parts

                if tag.upper() == "INPUT":
                    # Use the model's true input quantization
                    self.in_scale = float(scale_str)
                    self.in_zero = int(zero_str)

        except Exception:
            # If anything goes wrong, keep fallback values.
            return

    def close(self):
        """Release the camera."""
        try:
            self.picam2.close()
        except Exception:
            pass

    @staticmethod
    def _resize_nn(img: np.ndarray, new_h: int, new_w: int) -> np.ndarray:
        """Nearest-neighbor resize (fast + no external libraries)."""
        h, w = img.shape[:2]
        ys = (np.linspace(0, h - 1, new_h)).astype(np.int32)
        xs = (np.linspace(0, w - 1, new_w)).astype(np.int32)
        return img[ys][:, xs]

    def _preprocess_to_int8(self, frame: np.ndarray) -> np.ndarray:
        """
        Convert camera frame -> int8 tensor bytes expected by the C++ runner.

        Steps:
        - drop alpha channel (Picamera2 often gives XBGR8888 -> 4 channels)
        - convert to RGB
        - resize to 96x96 (your model input size)
        - normalize to [0..1]
        - quantize to int8 using the model's TRUE in_scale/in_zero (best accuracy)
        """
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3]  # drop alpha

        rgb = frame[:, :, ::-1]  # BGR-ish -> RGB
        rgb_small = self._resize_nn(rgb, 96, 96)  # uint8
        x = rgb_small.astype(np.float32) / 255.0  # [0..1]

        # Quantize float -> int8
        q = np.round(x / self.in_scale + self.in_zero).astype(np.int32)
        q = np.clip(q, -128, 127).astype(np.int8)
        return q  # shape (96,96,3) int8

    def scan(self, raw_input: str = ""):
        """
        Run ONE scan:
        - capture a frame
        - preprocess -> int8 bytes
        - call the C++ inference program
        - parse: "<label> <confidence>"

        Also updates:
        - self.last_label / self.last_conf (so GUI can show last result)
        """
        # Capture one frame
        frame = self.picam2.capture_array()

        # Preprocess -> int8 bytes
        q = self._preprocess_to_int8(frame)
        q.tofile(self.temp_frame_path)

        # Run inference binary
        try:
            result = subprocess.run(
                [self.runner_path, self.model_path, self.temp_frame_path],
                capture_output=True,
                text=True,
                check=False
            )
        except Exception:
            self.last_label = None
            self.last_conf = 0.0
            return None, 0.0

        if result.returncode != 0:
            # Debug tip:
            # print(result.stderr)
            self.last_label = None
            self.last_conf = 0.0
            return None, 0.0

        parts = result.stdout.strip().split()
        if len(parts) != 2:
            self.last_label = None
            self.last_conf = 0.0
            return None, 0.0

        label = parts[0]
        try:
            conf = float(parts[1])
        except ValueError:
            self.last_label = None
            self.last_conf = 0.0
            return None, 0.0

        # Save last result for GUI display
        self.last_label = label
        self.last_conf = conf

        return label, conf

    def capture_preview_frame(self):
        """
        Return a frame for GUI preview (no inference).
        The GUI will call this repeatedly to show live video.
        """
        return self.picam2.capture_array()