import datetime
import numpy as np
import cv2
from PIL import Image

# Only for RAW8 or RAW16 file of bayer color camera.
class SerVideo:
    EPOCH = datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
    BAYER_PATTERNS = {
        8: cv2.COLOR_BAYER_RGGB2RGB,
        9: cv2.COLOR_BAYER_GRBG2RGB,
        10: cv2.COLOR_BAYER_GBRG2RGB,
        11: cv2.COLOR_BAYER_BGGR2RGB
    }
    def read_int(self, f, n):
        return int.from_bytes(f.read(n), 'little')
    def int_to_timestamp(self, t8):
        return self.EPOCH + datetime.timedelta(microseconds=t8/10)
    def read_timestamp(self, f):
        return self.int_to_timestamp(self.read_int(f, 8))

    def __init__(self, input):
        f = open(input, "rb")
        file_id = f.read(14).decode(encoding='utf-8')
        lu_id = self.read_int(f, 4)
        self.color_id = self.read_int(f, 4)
        self.little_endian = self.read_int(f, 4)
        self.image_width = self.read_int(f, 4)
        self.image_height = self.read_int(f, 4)
        self.pixel_depth = self.read_int(f, 4)
        self.frame_count = self.read_int(f, 4)
        self.observer = f.read(40).decode(encoding='utf-8')
        self.instrume = f.read(40).decode(encoding='utf-8')
        self.telescope = f.read(40).decode(encoding='utf-8')
        self.date_time = self.read_int(f, 8)
        self.date_time_utc = self.read_int(f, 8)

        if self.date_time == 0:
            raise RuntimeError(f"SER file '{input}' has no frame timestamps.")

        self.frame_length = \
            self.image_width * self.image_height * self.pixel_depth//8
        if self.pixel_depth == 8:
            self.dtype = np.dtype('u1')
        elif self.pixel_depth == 16:
            self.dtype = np.dtype('u2')
        else:
            raise RuntimeError(f"Unsupported pixel depth: {self.pixel_depth}")

        if self.little_endian == 0:
            self.dtype = self.dtype.newbyteorder('>')
        else:
            self.dtype = self.dtype.newbyteorder('<')
        
        self.timestamps = []
        f.seek(178 + self.frame_count * self.frame_length)
        for p in range(self.frame_count):
            self.timestamps.append(self.read_timestamp(f))
        self.f = f

    def timestamp_of_frame_number(self, frame_number):
        return self.timestamps[frame_number - 1]

    def image_of_frame_number(self, frame_number):
        self.f.seek(178 + (frame_number - 1) * self.frame_length)
        array = np.frombuffer(self.f.read(self.frame_length), dtype=self.dtype)
        image_array = np.reshape(array, (self.image_height, self.image_width))
        cv2_image = cv2.cvtColor(image_array, self.BAYER_PATTERNS[self.color_id])
        return Image.fromarray(cv2_image)

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self):
        self.close()
