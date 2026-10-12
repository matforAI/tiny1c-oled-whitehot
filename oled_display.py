#!/usr/bin/env python3
import sys
import time
import spidev
import numpy as np
from PIL import Image
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from waveshare_OLED import OLED_0in95_rgb

W, H = 256, 192
PACKET = 512

# Tiny1-C: SPI CE0
cam = spidev.SpiDev()
cam.open(0, 0)
cam.mode = 3
cam.max_speed_hz = 16000000
cam.lsbfirst = False

def palette(v):
    if v < 64:
        return 0, 0, int(v * 4)
    elif v < 128:
        return 0, int((v - 64) * 4), 255 - int((v - 64) * 4)
    elif v < 192:
        return int((v - 128) * 4), 255, 0
    return 255, 255 - int((v - 192) * 4), 0

LUT = np.array([palette(i) for i in range(256)], dtype=np.uint8)

def get_frame():
    # Ищем начало кадра
    for _ in range(50):
        rx = bytes(cam.xfer2([0xAA] + [0] * 511))
        if rx[480] == 1:
            frame_no = rx[482] | (rx[483] << 8)
            break
    else:
        return None

    data = bytearray()
    for _ in range(H):
        data.extend(cam.xfer2([0x55] + [0] * 511))

    vals = np.frombuffer(data, dtype="<u2").reshape(H, PACKET // 2)
    return frame_no, vals[:, :W]

disp = None

try:
    # OLED: SPI CE1, RES GPIO24, D/C GPIO25
    disp = OLED_0in95_rgb.OLED_0in95_rgb()
    disp.Init()
    disp.clear()

    # Быстрая передача изображения блоками вместо байта за байтом
    def fast_show_image(buf):
        disp.SetWindows(0, 0, disp.width, disp.height)
        disp.digital_write(disp.DC_PIN, True)
        raw = bytes(buf)
        for i in range(0, len(raw), 1024):
            disp.spi.writebytes(list(raw[i:i + 1024]))

    disp.ShowImage = fast_show_image

    print("Tiny1-C -> OLED: быстрый режим. Ctrl+C для выхода.", flush=True)

    while True:
        result = get_frame()
        if result is None:
            continue

        _, vals = result
        lo = float(np.percentile(vals, 2))
        hi = float(np.percentile(vals, 98))

        if hi <= lo:
            lo, hi = float(vals.min()), float(vals.max())

        # WHITE HOT: горячее = белое, холодное = чёрное
        gray = (
            (vals.astype(np.float32) - lo)
            * (255.0 / max(1.0, hi - lo))
        ).clip(0, 255).astype(np.uint8)

        # RGB-изображение в оттенках серого для OLED
        rgb = np.repeat(gray[:, :, None], 3, axis=2)
        img = Image.fromarray(rgb, "RGB")
        img = img.transpose(Image.Transpose.ROTATE_180)
        img = img.resize((96, 64), Image.Resampling.BILINEAR)

        disp.ShowImage(disp.getbuffer(img))

except KeyboardInterrupt:
    print("\nОстановка.")

finally:
    if disp is not None:
        try:
            disp.clear()
            disp.module_exit()
        except Exception:
            pass
    cam.close()
