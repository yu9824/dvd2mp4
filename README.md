# dvd2mp4

Small utility to convert DVD VOB files (VIDEO_TS / VTS_*.VOB) into MP4 using
ffmpeg and ffprobe.

## Requirements

- Python 3.6+
- ffmpeg (available on PATH)
- ffprobe (available on PATH)

On macOS you can install ffmpeg with Homebrew:

```bash
brew install ffmpeg
```

## Usage

Place the DVD files (VIDEO_TS.BUP, VIDEO_TS.IFO, VTS_*.VOB, ...) in a
folder and run the script pointing to that folder.

Single combined MP4 (default output name is `<input_dirname>.mp4`):

```bash
python3 dvd2mp4.py -i /path/to/VIDEO_TS
```

Specify output filename:

```bash
python3 dvd2mp4.py -i /path/to/VIDEO_TS -o my_movie.mp4
```

Split by VTS prefix (create separate MP4 files per VTS group):

```bash
python3 dvd2mp4.py -i /path/to/VIDEO_TS -s
```

Enable verbose logging to see ffmpeg/ffprobe commands:

```bash
python3 dvd2mp4.py -i /path/to/VIDEO_TS -v
```

## Notes

- The script concatenates VOB files into a temporary file before
  transcoding. Temporary files are removed automatically.
- The first audio stream discovered by `ffprobe` is used for the output.
- Existing output files will be overwritten by ffmpeg (`-y` flag).

## Troubleshooting

- If you see "ffmpeg not found" or "ffprobe not found", ensure both are
  installed and on your PATH.
- If conversion fails with a non-zero exit status, the script prints the
  subprocess stderr and exits with code 1.

## License

MIT
