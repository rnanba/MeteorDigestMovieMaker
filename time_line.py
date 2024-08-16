from mdmm_file import MdmmData

class TimeLine:
    def __init__(self, mdmm_data, margin_before_frames, margin_after_frames):
        self.data = mdmm_data
        self.margin_before = margin_before_frames
        self.margin_after = margin_after_frames

    def is_frame_to_skip(self, frame_number):
        for r in self.data.ranges:
            start, end = r
            start -= self.margin_before
            end += self.margin_after
            if start <= frame_number and frame_number <= end:
                return False
        return True

    def increment_count(self, frame_number):
        inc = 0
        for r in self.data.ranges:
            start, end = r
            if start == frame_number:
                inc += 1
        return inc

    def is_scene_change(self, frame_number):
        is_start = False
        for r in self.data.ranges:
            start, end = r
            start -= self.margin_before
            if start < 1:
                start = 1
            end += self.margin_after
            if is_start:
                if start < frame_number and frame_number <= end:
                    return False
                else:
                    continue
            elif start == frame_number:
                is_start = True
            
        return is_start

    def is_last_frame_to_show(self, frame_number):
        is_end = False
        for r in self.data.ranges:
            start, end = r
            start -= self.margin_before
            end += self.margin_after
            if is_end:
                if frame_number < end:
                    return False
                else:
                    continue
            elif frame_number == end:
                is_end = True
                
        return is_end

    def ranges_starts_with(self, frame_number):
        ranges = None
        for r in self.data.ranges:
            start, _ = r
            if start == frame_nubmer:
                if ranges is None:
                    ranges = []
                ranges.append(r)
        return ranges

