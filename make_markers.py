#!/usr/bin/env python
import argparse
import sys
import glob
import os.path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageColor
import scipy.ndimage as ni

import mdmm_file
from time_line import TimeLine
from ser import SerVideo

def box_distance(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    dx = max(0, max(ax1, bx1) - min(ax2, bx2))
    dy = max(0, max(ay1, by1) - min(ay2, by2))
    return (dx**2 + dy**2) ** 0.5

def merge_box(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return (min(ax1,bx1), min(ay1,ay1), max(ax2,bx2), max(ay2,by2))

def merge_boxes(boxes, dist):
    groups = []
    def find_group(n):
        for g in groups:
            if n in g:
                return g
        return None
    
    for i in range(len(boxes)):
        g = find_group(i)
        if g is None:
            g = [i]
            groups.append(g)
        for j in range(i+1, len(boxes)):
            if box_distance(boxes[i], boxes[j]) < dist:
                jg = find_group(j)
                if jg:
                    g += jg
                    groups.remove(jg)
                else:
                    g.append(j)
    merged = []
    for g in groups:
        box = None
        for i in g:
            box = merge_box(box, boxes[i]) if box else boxes[i]
        merged.append(box)
    return merged

VERSION = '0.4'

BG_MAX = 16

ver_parser = argparse.ArgumentParser(add_help=False)
ver_parser.add_argument("--version", action="store_true")
known_args, unknown_args = ver_parser.parse_known_args()
if known_args.version:
    print(f"version {VERSION}")
    exit(0)

parser = argparse.ArgumentParser(parents=[ver_parser])
parser.add_argument("mdmm_filename", help="MDMM text files.")
parser.add_argument("--base-dir", default=".",
                    help="Base directory of filenames in MDMM file.")
parser.add_argument("--out-dir", default=".",
                    help="Directory to save output files.")
parser.add_argument("--max-bg-frames", type=int, default=16,
                    help="max background frames.")
parser.add_argument("--min-sigma-factor", type=float, default=3.0,
                    help="min sigma factor to detect transient light.")
parser.add_argument("--max-sigma-factor", type=float, default=9.0,
                    help="min sigma factor to detect transient light.")
parser.add_argument("--sigma-factor-step", type=float, default=1.0,
                    help="min sigma factor to detect transient light.")
parser.add_argument("--max-label-count", type=int, default=100,
                    help="max label count of detaction.")
parser.add_argument("--max-merge-distance", type=int, default=10,
                    help="max distance of small structures to merge.")
parser.add_argument("--min-structure-area", type=int, default=16,
                    help="min area of merged structure to select.")
parser.add_argument("--marker-color", default="#00FF00",
                    help="HTML color of marker outline.")
parser.add_argument("--marker-width", type=int, default=2,
                    help="width of marker outline.")
args = parser.parse_args()

if not os.path.exists(args.out_dir):
    os.makedirs(args.out_dir)

mdmm = mdmm_file.parse(args.mdmm_filename, args.base_dir)
basename = os.path.splitext(os.path.basename(args.mdmm_filename))[0]
base_marker_filename = f"{basename}_markers.json"
marker_file = os.path.join(args.out_dir, base_marker_filename)
marker_data = []

draw_color = ImageColor.getrgb(args.marker_color) + (128,)

for data in mdmm:
    print(f"from {data.rel_movie_file}:")
    file_entry = { "file": data.rel_movie_file, "ranges": [] }
    marker_data.append(file_entry)
    ser = SerVideo(data.movie_file)
    tl = TimeLine(data, 0, 0)
    for r in data.ranges:
        start, end = r
        print(f"  {start}:{end}")
        range_entry = { "range": [start, end], "markers": [] }
        file_entry["ranges"].append(range_entry)
        # range の直近のフレームで他の range と重ならない部分を背景値
        # 計算用に使う。
        bg_start = start
        bg_count = 0
        while bg_count < BG_MAX and bg_start > 1:
            if tl.is_frame_to_skip(bg_start - 1):
                bg_start -= 1
                bg_count += 1
            else:
                break
        bg_end = end
        if bg_count < args.max_bg_frames and bg_end < ser.frame_count:
            if tl.is_frame_to_skip(bg_end + 1):
                bg_end += 1
                bg_count += 1
            else:
                break
        if bg_count < BG_MAX:
            print("WARN: background reference frame is fewer than "\
                  f"{args.max_bg_frames}: {bg_count}")

        bg_frames = []
        print("    load background frames: "\
              f"{bg_start}:{start-1}, {end+1}:{bg_end}")
        for n in range(bg_start, start - 1):
            gray = ser.image_of_frame_number(n).convert("L")
            frame = np.asarray(gray, dtype=np.float32)
            bg_frames.append(frame)
        for n in range(end + 1, bg_end):
            gray = ser.image_of_frame_number(n).convert("L")
            frame = np.asarray(gray, dtype=np.float32)
            bg_frames.append(frame)
        
        print(f"    extract background")
        stack = np.stack(bg_frames, axis=0)
        bg = np.median(stack, axis=0)
        mad = np.median(np.abs(stack - bg), axis=0)
        sigma = np.maximum(1.4826 * mad, 1e-3)
        
        print(f"    load meteor frames")
        max_frame = None
        mode = None
        for n in range(start, end):
            #print(f"      frame[{n}]")
            gray = ser.image_of_frame_number(n).convert("L")
            if mode is None:
                mode = gray.mode
            frame = np.asarray(ni.median_filter(gray, size=5), dtype=np.float32)
            if max_frame is None:
                max_frame = frame
            else:
                max_frame = np.maximum(frame, max_frame)
        k = None
        if k is None:
            k_range = np.arange(args.min_sigma_factor,
                                args.max_sigma_factor,
                                args.sigma_factor_step)
        else:
            k_range = np.arange(k, k)
        for k in k_range:
            mask = (max_frame - bg) > k * sigma
            count = ni.convolve(mask.astype(np.uint8),
                                np.ones((3,3)), np.uint8, mode='constant')
            mask = mask & (count >= 3)
            mask = ni.binary_closing(mask, np.ones((3,3)))
            labeled, nn = ni.label(mask)
            if nn < args.max_label_count:
                break
            
        result_mask = np.zeros_like(mask)
        print(f"    label {nn} areas (k={k})")
        nnn = 0
        for i in range(1, nn + 1):
            if np.sum(labeled == i) >= 3:
                nnn += 1
                result_mask |= (labeled == i)
        print(f"    {nnn} labels selected")
        
        result = np.zeros_like(max_frame)
        result[result_mask] = max_frame[result_mask]
        result_8bit = result.astype(np.uint8)
        result_img = Image.fromarray(result_8bit, mode).convert("RGBA")
        
        result_bin = result_8bit > 0
        meteor_labeled, mn = ni.label(ni.binary_closing(result_bin, np.ones((5,5))))
        print(f"    {mn} structures detected")
        boxes = []
        mnn = 0
        for obj in ni.find_objects(meteor_labeled):
            yy, xx = obj
            area = (xx.stop - xx.start) * (yy.stop - yy.start)
            if area > 4:
                mnn += 1
                # draw.rectangle([(xx.start, yy.start), (xx.stop, yy.stop)],
                #                outline=(255,255,0,128), width=1)
                boxes.append((xx.start, yy.start, xx.stop, yy.stop))
        print(f"    {mnn} structures selected")

        print(f"    merge small structures")
        markers = range_entry["markers"]
        for box in merge_boxes(boxes, args.max_merge_distance):
            x1,y1,x2,y2 = box
            if (x2-x1)*(y2-y1) > args.min_structure_area:
                markers.append({ "rect": [x1,y1,x2,y2],
                                 "color": args.marker_color,
                                 "width": args.marker_width })
                print(f"      draw marker: ({x1}, {y1}), ({x2}, {y2})")
                overlay = Image.new("RGBA", (x2-x1+1, y2-y1+1), (0,0,0,0))
                draw = ImageDraw.Draw(overlay)
                draw.rectangle([(0,0),(x2-x1,y2-y1)],
                               outline=draw_color,
                               width=args.marker_width)
                result_img.alpha_composite(overlay, dest=(x1,y1))
        
        out = f"{data.rel_movie_file.replace('/','_')}-{start}_{end}.png"
        print(f"    save {out}")
        result_img.save(os.path.join(args.out_dir, out))

with open(marker_file, 'w') as f:
    json.dump(marker_data, f, indent=2)
    print(f"save {base_marker_filename}")
