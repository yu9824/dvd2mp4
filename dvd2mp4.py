#!/usr/bin/env python3
"""dvd2mp4

Utilities to convert DVD VOB files (VIDEO_TS/VTS_*.VOB) into MP4 using
ffmpeg/ffprobe.

This module provides a small CLI (``main``) and helper functions to:

- run shell commands safely with optional output capture and verbose logging
- concatenate multiple VOB files into a temporary container
- select an audio stream and transcode the video/audio into an MP4 file

Requirements
----------
ffmpeg, ffprobe : executables available on PATH

Examples
--------
Convert a DVD folder into a single MP4:

    python dvd2mp4.py -i /path/to/VIDEO_TS

Split by VTS prefix and create multiple MP4s:

    python dvd2mp4.py -i /path/to/VIDEO_TS -s

"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict


def run_command(cmd, verbose=False, capture_output=False):
    """Run a shell command with optional capture and verbose logging.

    This is a thin wrapper around :func:`subprocess.run` that normalizes
    behavior for the rest of the module. When ``verbose`` is True the
    command is printed to stdout and ffmpeg/ffprobe log messages are
    streamed to the terminal. When ``capture_output`` is True the
    function will return the command's standard output as a string;
    otherwise it returns ``None`` on success.

    Parameters
    ----------
    cmd : sequence
        Command to execute (list or tuple of program and arguments).
    verbose : bool, optional
        If True, print the command and stream subprocess output to the
        terminal. Default is False.
    capture_output : bool, optional
        If True, capture and return stdout as a text string. Default is
        False.

    Returns
    -------
    str or None
        Captured stdout when ``capture_output`` is True, otherwise
        ``None``.

    Raises
    ------
    SystemExit
        Exits with code 1 if the subprocess returns a non-zero exit
        status.
    """
    if verbose:
        print("▶", " ".join(cmd))
        if capture_output:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
            )
            return result.stdout
        else:
            subprocess.run(cmd, check=True)
            return None
    else:
        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE
                if capture_output
                else subprocess.DEVNULL,
                stderr=subprocess.PIPE
                if capture_output
                else subprocess.DEVNULL,
                text=True,
            )
            return result.stdout if capture_output else None
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {' '.join(cmd)}", file=sys.stderr)
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            sys.exit(1)


def convert_vobs_to_mp4(vob_files, output_file, verbose=False, aspect=None):
    """Concatenate VOB files and transcode them to an MP4 file.

    The function concatenates the provided VOB files into a single
    temporary file, probes available audio streams using ``ffprobe``,
    and then runs ``ffmpeg`` to transcode the video to H.264 and audio
    to AAC. The first audio stream found is used.

    Parameters
    ----------
    vob_files : list of str
        Ordered list of VOB file paths to concatenate and transcode.
    output_file : str
        Path to write the resulting MP4 file. If a file exists it will
        be overwritten.
    verbose : bool, optional
        If True, print progress messages and ffmpeg/ffprobe commands.
        Default is False.
    aspect : str or None, optional
        Manually specify an output aspect ratio (e.g. "16:9" or "4:3").
        When None the function will attempt to autodetect the aspect
        ratio using ffprobe.

    Notes
    -----
    - Requires ``ffmpeg`` and ``ffprobe`` to be available in PATH.
    - Uses a temporary directory to store the concatenated VOB prior
      to transcoding; temporary files are removed automatically.

    Examples
    --------
    >>> convert_vobs_to_mp4(["VTS_01_1.VOB", "VTS_01_2.VOB"], "out.mp4")
    """
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
        ffprobe_audio = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            concat_vob,
        ]
        audio_streams = run_command(
            ffprobe_audio, verbose=verbose, capture_output=True
        )
        if not audio_streams:
            print(
                f"❌ No audio streams found in {concat_vob}", file=sys.stderr
            )
            return
        audio_stream = audio_streams.strip().splitlines()[0]
        if verbose:
            print(f"🔊 Using audio stream: {audio_stream}")

        # アスペクト比: ユーザー指定があればそれを使い、なければ ffprobe で自動検出
        dar = None
        if aspect:
            dar = aspect
            if verbose:
                print(f"📐 Using user-specified aspect ratio: {dar}")
        else:
            ffprobe_video = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=display_aspect_ratio",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                concat_vob,
            ]
            dar = run_command(
                ffprobe_video, verbose=verbose, capture_output=True
            )
            dar = dar.strip() if dar else None
            if verbose and dar:
                print(f"📐 Detected aspect ratio: {dar}")

        # ffmpeg変換
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            concat_vob,
            "-map",
            "0:v:0",
            "-map",
            f"0:{audio_stream}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
        ]
        if dar:
            ffmpeg_cmd += ["-aspect", dar]

        ffmpeg_cmd.append(output_file)
        run_command(ffmpeg_cmd, verbose=verbose)

        if verbose:
            print(f"✅ Created {output_file}")


def main():
    """Command line entry point.

    Parses command line arguments and invokes conversion routines. When
    invoked as a script this function performs basic validation of the
    input directory and presence of external tools, and either creates
    a single combined MP4 or multiple MP4s split by VTS prefix.

    Command line options
    --------------------
    - ``-i/--input`` : path to the DVD folder containing VTS_*.VOB files
    - ``-o/--output`` : output filename for single-file mode
    - ``-s/--split`` : split into separate MP4 files per VTS prefix
    - ``-v/--verbose`` : enable verbose logging

    Returns
    -------
    None
    """
    parser = argparse.ArgumentParser(
        description="Convert DVD VOB files to MP4 using ffmpeg"
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to DVD structure directory containing VTS_??_*.VOB files",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output MP4 filename (default: <input_dirname>.mp4)",
    )
    parser.add_argument(
        "-s",
        "--split",
        action="store_true",
        help="Split by VTS prefix (generate multiple MP4 files)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "-a",
        "--aspect",
        help=(
            "Manually specify output aspect ratio (e.g. 16:9 or 4:3). "
            "If omitted the script will attempt to autodetect via ffprobe."
        ),
    )
    args = parser.parse_args()

    # ffmpeg / ffprobe check
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(
                f"Error: {tool} not found in PATH. Please install it.",
                file=sys.stderr,
            )
            sys.exit(1)

    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(
            f"Error: input directory not found: {input_dir}", file=sys.stderr
        )
        sys.exit(1)

    vob_files = sorted(glob.glob(os.path.join(input_dir, "VTS_??_*.VOB")))
    if not vob_files:
        print(
            f"Error: no VTS_??_*.VOB files found in {input_dir}",
            file=sys.stderr,
        )
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
            convert_vobs_to_mp4(
                files, output_file, verbose=args.verbose, aspect=args.aspect
            )

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

        convert_vobs_to_mp4(
            vob_files, output_file, verbose=args.verbose, aspect=args.aspect
        )


if __name__ == "__main__":
    main()
