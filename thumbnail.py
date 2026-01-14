# Auto generates thumbnails relative to a given directory.

import argparse
import pathlib
import time
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

    print(f"generating thumbnails...")
    thumbDir.mkdir(parents=True, exist_ok=True)
    startTime = time.time()
    generate_thumbnails(thumbnailGenerationData)
    endTime = time.time()
    print(f"\ncompleted in {endTime - startTime} seconds")

def generate_thumbnails(thumbnailGenerationData: list[tuple[pathlib.Path, pathlib.Path, int, int]]) -> None:
    numProcesses = mp.cpu_count()
    with mp.Pool(numProcesses) as pool:
        mp.freeze_support()
        numImages = len(thumbnailGenerationData)
        counter = 0
        for _ in pool.imap_unordered(generate_thumbnail, thumbnailGenerationData):
            counter += 1
            print(f"processed {counter}/{numImages} images", end="\r")
        
def generate_thumbnail(thumbGenData: tuple[pathlib.Path, pathlib.Path, int, int]) -> None:
    sourcePath, targetPath, width, quality = thumbGenData
    thumb: pv.Image = pv.Image.thumbnail(sourcePath, width)
    pv.Image.heifsave(thumb, targetPath, Q=quality)

if __name__ == "__main__":
    main()