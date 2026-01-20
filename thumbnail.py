# Auto generates thumbnails relative to a given directory.

# stdlib imports
from pathlib import Path
import argparse
import atexit
import json
import logging.config
import multiprocessing as mp
import os

# Third party 
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import boto3
import pyvips as pv

logger = logging.getLogger("gallery_util")

load_dotenv()

def init_logging():
    config_file = Path("logConfig.json")
    with open(config_file) as cf:
        config = json.load(cf)
    logging.config.dictConfig(config)
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)

def main():
    init_logging()

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Source directory or filename")
    parser.add_argument("-w", "--width", type=int, help="Width of thumbnail to generate (default: 1000px)")
    parser.add_argument("-q", "--quality", type=int, help="Compression factor for thumbnail output (default: 75)")
    parser.add_argument("-e", "--effort", type=int, help="CPU effort spent improving compression (0: fastest, 9: slowest, 4: default)")
    parser.add_argument("-c", "--collection", type=str, help="Collection(s) to add photos to (use ; to delimit collections)")
    parser.add_argument("-o", "--overwrite", action="store_true", help="Disable smart thumbnail generation and overwrite stored images")
    parser.add_argument("-oo", "--offlineOnly", action="store_true", help="Disable uploading and only generate thumbnails locally")
    parser.add_argument("-uo", "--uploadOnly", action="store_true", help="Skip thumbnail generation and only upload to D1 and R2")
    args = parser.parse_args()

    # Define thumbnail export settings
    width = 1000 if not args.width else max(64, int(args.width))
    quality = 75 if not args.quality else max(0, min(100, int(args.quality)))
    effort = 4 if not args.effort else max(0, min(9, int(args.effort)))
    exportSettings = (width, quality, effort)
    sourcePath = Path(args.source)
    overwrite = bool(args.overwrite)

    # Generate path for all thumbnails
    pathData = []
    logger.info(f"Scanning path: {sourcePath}")
    if sourcePath.is_dir():
        logger.info("Path provided is a DIRECTORY")
        sourceDir = sourcePath
        thumbDir = sourceDir / "thumbnails"
        for filePath in sourceDir.iterdir():
            if filePath.is_file():
                thumbPath = thumbDir / ".".join((filePath.name.rsplit(".")[0] + "-thumb", "avif"))
                # Do not regenerate thumbnail unless overwrite flag is enabled
                if overwrite or not thumbPath.exists():
                    pathData.append((filePath, thumbPath))
    else:
        logger.info("Path provided is a FILE")
        sourceDir = sourcePath.parent
        thumbDir = sourceDir / "thumbnails"
        thumbPath = thumbDir / ".".join((sourcePath.name.rsplit(".")[0] + "-thumb", "avif"))
        if overwrite or not thumbPath.exists():
            pathData.append((sourcePath, thumbPath))

    logger.info(f"Found {len(pathData)} files")

    if not pathData:
        logger.info("No new thumbnails found. Exiting early.")
        return 0

    if not args.uploadOnly:
        thumbnailGenerationData = [(pd, exportSettings) for pd in pathData]
        thumbDir.mkdir(parents=True, exist_ok=True)
        generate_thumbnails(thumbnailGenerationData)
    else:
        logger.info("Thumbnail generation DISABLED")

    if not args.offlineOnly:

        # Call API to push photo names to DB; return array of id(s) associated with photos
        logger.info("Updating thumbnail path tables...")
        
        # Upload photos and thumbnails to R2
        logger.info("Connecting to object storage...")
        aws_endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        s3 = boto3.client("s3", endpoint_url = aws_endpoint_url, region_name="auto")
        for source, thumbnail in pathData:
            push_to_r2(s3, source, thumbnail)

        # Create linking for photos to collections (optional)
        if args.collection:
            collections = args.collection.split()
    else:
        logger.info("File uploads DISABLED")

def generate_thumbnails(thumbnailGenerationData: list[tuple[tuple[Path, Path], tuple[int, int, int]]]) -> None:
    """
    Multiprocess thumbnail generation.
    """
    numProcesses = mp.cpu_count()
    with mp.Pool(numProcesses) as pool:
        mp.freeze_support()
        numImages = len(thumbnailGenerationData)
        counter = 0
        for _ in pool.imap_unordered(generate_thumbnail, thumbnailGenerationData):
            counter += 1
            print(f"processed {counter}/{numImages} images", end="\r")
        
def generate_thumbnail(thumbGenData: tuple[tuple[Path, Path], tuple[int, int, int]]) -> None:
    """
    Generates an `.avif` thumbnail with export settings applied.
    """
    pathData, exportSettings = thumbGenData
    sourcePath, targetPath = pathData
    width, quality, effort = exportSettings
    thumb: pv.Image = pv.Image.thumbnail(sourcePath, width, size=pv.Size.DOWN)
    pv.Image.heifsave(thumb, targetPath, Q=quality, compression="av1", effort=effort)

def push_to_r2(session, src: Path, thumbnail: Path):
    """
    Push source image and thumbnail to R2 via `boto3`
    """
    try:
        session.upload_file(src, os.getenv("S3_BUCKET_NAME"), src.name)
        session.upload_file(thumbnail, os.getenv("S3_BUCKET_NAME"), thumbnail.name)
    except ClientError as e:
        logger.error(e)

if __name__ == "__main__":
    main()