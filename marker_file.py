import sys
import os.path
import json

"""
[
  {
    "file": "dir/file.ser",
    "ranges": [
      { 
        "range": [start, end],
        "markers": [
          { "rect": [ x1, y1, x2, y2 ], "color": color, "width": width },
          ...
        ]
      }
      ...
    ]
  }
  ...
]
"""

class MarkerFileData:
    def __init__(self, data):
        self.data = data

    def get_markers(self, rel_movie_file, frame_number, cue=0):
        result = []
        for f in self.data:
            if f["file"] == rel_movie_file:
                for r in f["ranges"]:
                    start, end = r["range"]
                    if (start - cue) <= frame_number and frame_number <= end:
                        result += r["markers"]
        return result
    
def parse(marker_file, base_dir):
    if not os.path.exists(base_dir):
        raise RuntimeError(f"ERROR: Base directory not found: {base_dir}")
    
    with open(marker_file, "r") as f:
        return MarkerFileData(json.load(f))
