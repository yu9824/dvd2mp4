#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
import subprocess
import tempfile
import glob
import re
from collections import defaultdict

def run_command(cmd, verbose=False, capture_output=False):
    if verbose:
        print("▶", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, check=True,
            capture_output=capture_output,
            text=True
        )
        return result.stdout if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {' '.join(cmd)}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)

def convert_vobs_to_mp4(vob_files, output_file, verbose=False):
    """VOBファイルを結合し、音声ストリームを選んでMP4に変換"""
    with tempfile.TemporaryDirectory() as tmpdir:
        concat_vob = os.path.join(tmpdir, "concat.VOB")
        # VOB結合
        with open(concat_vob, "wb") as outfile:
            for vf in vob_files:
                if verbose:
                    print(f"  ➕ {vf}")
                with open(vf, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)

        # 音声ストリーム取得
        ffprobe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "default=noprint_wrappers=1:nokey=1",
            concat_vob
        ]
        audio_streams = run_command(ffprobe_cmd, verbose=verbose, capture_output=True).strip().splitlines()
        if not audio_streams:
            print(f"❌ No audio streams found in {concat_vob}", file=sys.stderr)
            return
        audio_stream = audio_streams[0]
        if verbose:
            print(f"🔊 Using audio stream: {audio_stream}")

        # ffmpeg変換
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", concat_vob,
            "-map", "0:v:0", "-map", f"0:{audio_stream}",
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_file
        ]
        run_command(ffmpeg_cmd, verbose=verbose)
        if verbose:
            print(f"✅ Created {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Convert DVD VOB files to MP4 using ffmpeg"
    )
    parser.add_argument("-i", "--input", required=True,
                        help="Path to DVD structure directory containing VTS_??_*.VOB files")
    parser.add_argument("-o", "--output",
                        help="Output MP4 filename (default: <input_dirname>.mp4)")
    parser.add_argument("-s", "--split", action="store_true",
                        help="Split by VTS prefix (generate multiple MP4 files)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()

    # ffmpeg / ffprobe check
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(f"Error: {tool} not found in PATH. Please install it.", file=sys.stderr)
            sys.exit(1)

    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(f"Error: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    vob_files = sorted(glob.glob(os.path.join(input_dir, "VTS_??_*.VOB")))
    if not vob_files:
        print(f"Error: no VTS_??_*.VOB files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    if args.split:
        # プレフィックスごとにグループ化
        groups = defaultdict(list)
        for vf in vob_files:
            m = re.search(r"(VTS_\d{2})_\d+\.VOB$", vf)
            if m:
                groups[m.group(1)].append(vf)

        for prefix, files in sorted(groups.items()):
            files.sort()
            output_file = f"{prefix}.mp4"
            if args.verbose:
                print(f"📼 Processing group: {prefix} → {output_file}")
            convert_vobs_to_mp4(files, output_file, verbose=args.verbose)

    else:
        # すべて結合して1つのmp4
        output_file = args.output
        if not output_file:
            output_file = os.path.basename(input_dir.rstrip("/")) + ".mp4"
        output_file = os.path.abspath(output_file)

        if args.verbose:
            print(f"📂 Input dir: {input_dir}")
            print(f"📼 VOB files: {len(vob_files)} found")
            print(f"💾 Output: {output_file}")

        convert_vobs_to_mp4(vob_files, output_file, verbose=args.verbose)

if __name__ == "__main__":
    main()
