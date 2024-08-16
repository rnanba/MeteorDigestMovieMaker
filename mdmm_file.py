import os.path
import re

class MdmmData:
    def __init__(self, movie_file):
        self.movie_file = movie_file
        self.ranges = []

    def append(self, start, end):
        self.ranges.append((start, end))

    def sort(self):
        self.ranges.sort()

def parse(mdmm_file, base_dir):
    if not os.path.exists(base_dir):
        raise RuntimeError(f"ERROR: Base directory not found: {base_dir}")

    mdmm = []
    with open(mdmm_file, "r") as f:
        path = []
        data = None
        line_number = 0
        for line in f:
            line_number += 1
            if m := re.match(r"^(#+)\s*(.+)\s*$", line):
                level_mark, filename = m.groups()
                level = len(level_mark)
                if level == len(path)+1:
                    path.append(filename)
                elif level <= len(path):
                    if data is not None:
                        data.sort()
                        data = None
                    for _ in range(len(path) - level):
                        path.pop()
                    path.pop()
                    path.append(filename)
                else:
                    raise RuntimeError(f"ERROR: {mmdm_file}:{line_number}:"\
                                       " An inconsistency in nesting level"\
                                       " is detected.\n> {line}")
            elif m := re.match(r"^([0-9]+)\s*:\s*([0-9]+)\s*.*$", line):
                start, end = m.groups()
                if data is None:
                    movie_file = os.path.join(base_dir, *path)
                    if not os.path.exists(movie_file):
                        raise RuntimeError(f"ERROR: Movie file '{movie_file}'"\
                                           " is not found.")
                    data = MdmmData(movie_file)
                    mdmm.append(data)

                data.append(int(start), int(end))
            elif re.match(r"^\s*$", line):
                continue
            else:
                raise RutimeError(f"ERROR: {mmdm_file}:{line_number}:"\
                                  " Unexpected line.\n> {line}")
        if data is not None:
            data.sort()

    return mdmm
        
