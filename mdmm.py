#!/usr/bin/env python
import argparse
import sys
import glob
import os.path
import platform
import datetime
import fractions
import numpy as np
import av
from PIL import Image, ImageColor, ImageDraw, ImageFont
import mdmm_file
import marker_file
from time_line import TimeLine
from ser import SerVideo

VERSION = '0.4'

FONTS = {
    "Linux": "Courier_New.ttf",
    "Windows": "cour.ttf",
    "Darwin": "Courier.ttc"
}
TEXT_ANCHORS = {
    "top-left": "la",
    "top-middle": "ma",
    "top-right": "ra",
    "bottom-left": "ld",
    "bottom-middle": "md",
    "bottom-right": "rd"
}

LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo

def abort(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

def get_font(font_filename, font_size):
    if font_filename is None:
        if platform.system() not in FONTS:
            abort("ERROR: Default font of OS is not detected."\
                  " Please specify font filename with --font.")
        else:
            font_filename = FONTS[platform.system()]
    
    return ImageFont.truetype(font_filename, font_size)

def test_text_position(pos):
    if pos not in TEXT_ANCHORS:
        pos_keys = None
        for pos_key in TEXT_ANCHORS.keys():
            if pos_keys is None:
                pos_keys = ""
            else:
                pos_keys += ", "
            pos_keys += f"'{pos_key}'"
        abort(f"ERROR: Unknown text position: '{pos}'. Specify {pos_keys}.")
    return True
    
def get_text_position(pos, width, height):
    if pos =="top-left":
        return (0, 0)
    elif pos == "top-middle":
        return (width/2, 0)
    elif pos == "top-right":
        return (width, 0)
    elif pos == "bottom-left":
        return (0, height)
    elif pos == "bottom-middle":
        return (width/2, height)
    elif pos == "bottom-right":
        return (width, height)
    else:
        return None

def create_output_stream(container_out, width_in, height_in, args):
    bit_rate = None
    if args.video_bit_rate.endswith('M'):
        bit_rate = int(float(args.video_bit_rate[0:-1]) * 1000 * 1000)
    else:
        bit_rate = int(float(args.video_bit_rate))

    out_width = WIDTH = width_in
    out_height = HEIGHT = height_in
    if args.video_codec == "libx264":
        if WIDTH % 2 == 1:
            out_width -= 1
        if HEIGHT % 2 == 1:
            out_height -= 1
    fps = fractions.Fraction(args.frame_rate)
    stream_out = container_out.add_stream(args.video_codec,
                                          rate=fps)
    stream_out.bit_rate = bit_rate
    stream_out.width = out_width
    stream_out.height = out_height
    if args.timestamp_only and args.alpha:
        stream_out.pix_fmt = "yuva420p"
    else:
        stream_out.pix_fmt = "yuv420p"
    return stream_out

def draw_timestamp(draw, t, pos, anchor, font, color, in_cue, count=None):
    t_str = f"{str(t)}"
    x1, y1, x2, y2 = font.getbbox(t_str, anchor=anchor)
    c_str = ""
    xc = 0
    if count is not None:
        c_str = "" if count == 0 else str(count)
        c_str =  c_str.ljust(4)
        _, _, xc, _ = font.getbbox(c_str, anchor=anchor)
    draw.text(pos, f"{c_str}{t_str}", fill=color, font=font, anchor=anchor)
    if in_cue:
        cx1 = pos[0] + x1 + xc
        cx2 = pos[0] + x2 + xc
        cy = pos[1] + y2
        draw.line((cx1,cy,cx2,cy), fill=color, width=3)

def draw_marker(draw, marker, font_alpha=None):
    x1, y1, x2, y2 = marker["rect"]
    marker_color = ImageColor.getrgb(marker["color"])
    if font_alpha and len(marker_color) == 3:
        marker_color += (font_alpha,)
    draw.rectangle([(x1,y1),(x2,y2)], outline=marker_color, width=marker["width"])

def make_movie(mdmm_filename, args, font):
    mdmm = mdmm_file.parse(mdmm_filename, args.base_dir)
    name = os.path.splitext(os.path.basename(mdmm_filename))[0]
    marker_data = None
    if args.marker_file:
        marker_data = marker_file.parse(args.marker_file, args.base_dir)
    mode = ""
    if args.timestamp_only:
        mode = "_timestamp"
    if args.no_timestamp:
        mode = "_notimestamp"
    out_file = os.path.join(args.out_dir, f"{name}{mode}{args.out_ext}")
    if os.path.exists(out_file):
        abort(f"ERROR: Output file '{out_file}' is already exists.")
    print(f"{mdmm_filename} -> {out_file}")

    is_cropped_output = False
    font_color = ImageColor.getrgb(args.font_color)
    font_alpha = None
    if args.timestamp_only and args.alpha and len(font_color):
        font_alpha = font_color[3]
    text_anchor = TEXT_ANCHORS[args.text_position]
    text_pos = None
    container_out = None
    stream_out = None
    meteor_count = 0
    for data in mdmm:
        print(f"- {data.movie_file}: ", end="", flush=True)
        ser = SerVideo(data.movie_file)
        if container_out is None:
            container_out = av.open(out_file, mode="w")
            stream_out = create_output_stream(container_out,
                                              ser.image_width,
                                              ser.image_height,
                                              args)
            is_cropped_output = (ser.image_width != stream_out.width or
                                 ser.image_height != stream_out.height)
            text_pos = get_text_position(args.text_position,
                                         stream_out.width, stream_out.height)
        
        out_frame_rate = float(args.frame_rate)
        time_line = TimeLine(data,
                             int(float(args.margin_before) * out_frame_rate),
                             int(float(args.margin_after) * out_frame_rate))
        cue_frames = int(float(args.cue) * out_frame_rate)
        cue_end = 0
        count_inc = 0
        for frame_number in range(1, ser.frame_count+1):
            if time_line.is_frame_to_skip(frame_number):
                continue

            count_inc = time_line.increment_count(frame_number)
            meteor_count += count_inc
            image = None
            if args.timestamp_only:
                mode = "RGBA" if args.alpha else "RGB"
                bgcolor = "#00000000" if args.alpha else "#000000"
                image = Image.new(mode=mode, color=bgcolor,
                                  size=(stream_out.width, stream_out.height))
            else:
                image = ser.image_of_frame_number(frame_number)
                if is_cropped_output:
                    image = image.crop((0, 0,
                                        stream_out.width, stream_out.height))

            if time_line.is_scene_change(frame_number):
                cue_end = frame_number + cue_frames

            if not args.no_timestamp:
                draw = ImageDraw.Draw(image)
                if marker_data:
                    markers = marker_data.get_markers(data.rel_movie_file,
                                                      frame_number)
                    for m in markers:
                        draw_marker(draw, m, font_alpha)
                
                t = ser.timestamp_of_frame_number(frame_number)
                if args.localtime:
                    t = t.astimezone(LOCAL_TZ)
                c = meteor_count if args.meteor_count else None
                draw_timestamp(draw, t, text_pos, text_anchor, font, font_color,
                               cue_end > 0, c)
            if cue_end > 0:
                print("_", end="", flush=True)
            else:
                print(".", end="", flush=True)
            if count_inc > 0:
                print("+", end="", flush=True)
            
            if frame_number >= cue_end:
                cue_end = 0

            vf = None
            if args.timestamp_only:
                format = "rgba" if args.alpha else "rgb24"
                np_array = np.array(image)
                vf = av.VideoFrame.from_numpy_buffer(np_array, format=format)
            else:
                vf = av.VideoFrame.from_image(image)
            
            for packet in stream_out.encode(vf):
                container_out.mux(packet)
                
            if time_line.is_last_frame_to_show(frame_number):
                break
        
        ser.close()
        print("done")
        
    for packet in stream_out.encode():
        container_out.mux(packet)
    container_out.close()

#
ver_parser = argparse.ArgumentParser(add_help=False)
ver_parser.add_argument("--version", action="store_true")
known_args, unknown_args = ver_parser.parse_known_args()
if known_args.version:
    print(f"version {VERSION}")
    exit(0)

parser = argparse.ArgumentParser(parents=[ver_parser])
parser.add_argument("mdmm_files", nargs="+",
                    help="MDMM text files.")
parser.add_argument("frame_rate", 
                    help="Output frame rate.")
parser.add_argument("--base-dir", default=".",
                    help="Base directory of filenames in MDMM file.")
parser.add_argument("--out-dir", default=".",
                    help="Directory to save output files.")
parser.add_argument("--out-ext", default=".mp4",
                    help="Output file format extension.")
parser.add_argument("--font", default=None,
                    help="Font filename of frame count text.")
parser.add_argument("--font-size", type=int, default=24,
                    help="Font size (pixels) of frame count text.")
parser.add_argument("--font-color", default="#FF8888",
                    help="Font color of frame count text.")
parser.add_argument("--text-position", default="top-left",
                    help="Position of frame count text. The options 'top-left',"\
                    " 'top-middle', 'top-right', 'bottom-left', 'bottom-middle',"\
                    " and 'bottom-right' can be specified.")
parser.add_argument("--video-codec", default="libx264",
                    help="Output video codec.")
parser.add_argument("--video-bit-rate", default="12M",
                    help="Output video bit rate(bps)."\
                    " Suffix 'M' can be specified.")
parser.add_argument("--margin-before", type=float, default=2.0)
parser.add_argument("--margin-after", type=float, default=2.0)
parser.add_argument("--cue", type=float, default=0.5)
parser.add_argument("--localtime", action="store_true")
parser.add_argument("--meteor-count", action="store_true")
parser.add_argument("--no-timestamp", action="store_true")
parser.add_argument("--timestamp-only", action="store_true")
parser.add_argument("--alpha", action="store_true")
parser.add_argument("--marker-file", default=None,
                    help="output json file of make_markers.py")

args = parser.parse_args()

if args.no_timestamp and args.timestamp_only:
    abort("ERROR: --no-timestamp and --timestamp-only are exclusive options.")
    
font = None
if not args.no_timestamp:
    test_text_position(args.text_position)
    font = get_font(args.font, args.font_size)

if not os.path.exists(args.out_dir):
    os.makedirs(args.out_dir)

for pattern in args.mdmm_files:
    for mdmm_filename in glob.glob(pattern):
        make_movie(mdmm_filename, args, font)

