# Auto generates thumbnails relative to a given directory.

import argparse
import pathlib
import pyvips as pv
import multiprocessing as mp

def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Source directory or filename")
    parser.add_argument("-w", "--width", type=int, help="Width of thumbnail to generate (default: 1000px)")
    parser.add_argument("-q", "--quality", type=int, help="Quality setting for thumbnail output (default: 75)")
    args = parser.parse_args()

    thumbWidth = 1000 if not args.width else int(args.width)
    thumbQuality = 75 if not args.quality else int(args.quality)

    sourcePath = pathlib.Path(args.source)

    # Generate map of source image to thumbnail path
    if sourcePath.is_dir():
        sourceDir = sourcePath
        thumbDir = sourceDir / "thumbnails"
        thumbnailGenerationData = [(
            filePath, 
            thumbDir / ".".join((filePath.name.rsplit(".")[0] + "-thumb", "avif")),
            thumbWidth,
            thumbQuality
            ) for filePath in sourceDir.iterdir() if filePath.is_file()]
    else:
        sourceDir = sourcePath.parent
        thumbDir = sourceDir / "thumbnails"
        thumbnailGenerationData = [(
            sourcePath, 
            thumbDir / ".".join((sourcePath.name.rsplit(".")[0] + "-thumb", "avif")),
            thumbWidth,
            thumbQuality
            )]
    print(f"found {len(thumbnailGenerationData)} files")

    # Generate thumbnail directory if it does not already exist
    print(f"generating thumbnails...")
    thumbDir.mkdir(parents=True, exist_ok=True)
    generate_thumbnails(thumbnailGenerationData)
    print("complete")

def generate_thumbnails(thumbnailGenerationData: list[tuple[pathlib.Path, pathlib.Path]]) -> None:
    numProcesses = mp.cpu_count()
    with mp.Pool(numProcesses) as pool:
        mp.freeze_support()
        pool.starmap(generate_thumbnail, thumbnailGenerationData)

def generate_thumbnail(sourcePath, targetPath, width, quality) -> None:
    thumb: pv.Image = pv.Image.thumbnail(sourcePath, width)
    pv.Image.heifsave(thumb, targetPath, Q=quality)

def generate_manifest(sourceDir, sourceFiles):
    pass

if __name__ == "__main__":
    main()