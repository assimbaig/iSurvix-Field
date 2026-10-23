"""Keep local evidence processing opted out of native runtime telemetry."""
import os

# ONNX Runtime 1DS telemetry can initialize in native code at import time and
# bypass Python socket guards. Set its documented process-lifetime opt-out before
# any OCR/embedding adapter imports ONNX Runtime. This does not change inference.
os.environ['ORT_DISABLE_TELEMETRY'] = '1'
