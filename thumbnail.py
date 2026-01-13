# Auto generates thumbnails relative to a given directory.

import argparse
import pathlib
import pyvips as pv

def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Source directory or filename")
    parser.add_argument("-w", "--width", help="Width of thumbnail to generate (default: 1000px)")
    parser.add_argument("-q", "--quality", help="Quality setting for thumbnail output (default: 75)")
    args = parser.parse_args()

    # default; source is a sourceDir path
    sourcePath = pathlib.Path(args.source)
    if sourcePath.is_dir():
        sourceDir = sourcePath
        sourceFiles = {_.name: _ for _ in sourceDir.iterdir() if _.is_file()}
    else:
        sourceDir = sourcePath.parent
        sourceFiles = {sourcePath.name: sourcePath}
        
    thumbWidth = 1000 if not args.width else args.width
    thumbQuality = 75 if not args.quality else args.quality
    thumbDir = sourceDir / "thumbnails"
    thumbDir.mkdir(parents=True, exist_ok=True)
    print(f"found {len(sourceFiles)} files")
    print(f"generating thumbnails...")
    processed = 0
    for filename, filepath in sourceFiles.items():
        thumb: pv.Image = pv.Image.thumbnail(filepath, thumbWidth)
        thumbName = ".".join((filename.rsplit(".")[0] + "-thumb", "avif"))
        thumbPath = thumbDir / thumbName
        pv.Image.heifsave(thumb, thumbPath, Q=thumbQuality)
        processed += 1  
        print(f"{processed}/{len(sourceFiles)} processed", end="\r")
    print("\ncomplete")

if __name__ == "__main__":
    main()