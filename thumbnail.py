# Auto generates thumbnails relative to a given directory.

# stdlib imports
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
import argparse
import atexit
import json
import logging.config
import multiprocessing as mp
import os
import time

# Third party 
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from exif import Image
import boto3
import pyvips as pv
import requests

# Default thumbnail generation values
DEFAULT_WIDTH = 1000
DEFAULT_QUALITY = 75
DEFAULT_EFFORT = 4

# Cloudflare D1 parameter limit per batch query
BATCH_PARAM_LIMIT = 100

logger = logging.getLogger("gallery_util")

load_dotenv()

def init_logging():
    configFile = Path("logConfig.json")
    with open(configFile) as cf:
        config = json.load(cf)
    logging.config.dictConfig(config)
    queueHandler = logging.getHandlerByName("queue_handler")
    if queueHandler is not None:
        queueHandler.listener.start()
        atexit.register(queueHandler.listener.stop)

def main():
    init_logging()

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Source directory or filename")
    parser.add_argument("-w", "--width", type=int, help="Width of thumbnail to generate (default: 1000px)")
    parser.add_argument("-q", "--quality", type=int, help="Compression factor for thumbnail output (default: 75)")
    parser.add_argument("-e", "--effort", type=int, help="CPU effort spent improving compression (0: fastest, 9: slowest, 4: default)")
    parser.add_argument("-c", "--collections", type=str, help="Collection(s) to add photos to (use ; to delimit collections)")
    parser.add_argument("-oo", "--offlineOnly", action="store_true", help="Disable uploading and only generate thumbnails locally")
    parser.add_argument("-uo", "--uploadOnly", action="store_true", help="Skip thumbnail generation and only upload to D1 and R2")
    parser.add_argument("-t", "--test", action="store_true", help="For development testing")
    args = parser.parse_args()

    # Define thumbnail export settings
    width = DEFAULT_WIDTH if not args.width else max(64, int(args.width))
    quality = DEFAULT_QUALITY if not args.quality else max(0, min(100, int(args.quality)))
    effort = DEFAULT_EFFORT if not args.effort else max(0, min(9, int(args.effort)))
    exportSettings = (width, quality, effort)
    sourcePath = Path(args.source)

    metadata = defaultdict(lambda: defaultdict(lambda: "NULL")) # Map source file to metadata with default value=NULL

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
                pathData.append((filePath, thumbPath))
    else:
        logger.info("Path provided is a FILE")
        sourceDir = sourcePath.parent
        thumbDir = sourceDir / "thumbnails"
        thumbPath = thumbDir / ".".join((sourcePath.name.rsplit(".")[0] + "-thumb", "avif"))
        pathData.append((sourcePath, thumbPath))

    logger.info(f"Found {len(pathData)} files")

    if not pathData:
        logger.info("No new thumbnails found. Exiting early.")
        return 0

    # Testing
    if args.test:
        return 0

    # Generate thumbnails
    if not args.uploadOnly:
        thumbnailGenerationData = [(pd, exportSettings) for pd in pathData]
        thumbDir.mkdir(parents=True, exist_ok=True)
        generate_thumbnails(thumbnailGenerationData)
    else:
        logger.info("Thumbnail generation DISABLED")

    # Upload photos and metadata
    if not args.offlineOnly:
        # Call API to push photo names to DB; return array of id(s) associated with photos
        logger.info("Updating thumbnail path tables...")
        batch_metadata(pathData)
        
        # Upload photos and thumbnails to R2
        logger.info("Pushing images and thumbnails to object storage...")
        push_to_r2(pathData)

        # Create linking for photos to collections (optional)
        if args.collections:
            pass
    else:
        logger.info("File uploads DISABLED")

def generate_thumbnails(thumbnailGenerationData: list[tuple[tuple[Path, Path], tuple[int, int, int]]]) -> None:
    """
    Multiprocess thumbnail generation.
    """
    logger.info(f"Beginning thumbnail generation for {len(thumbnailGenerationData)} images")
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
    if (targetPath.is_file()): 
        logger.debug(f"Skipping thumbnail generation, {targetPath.name} already exists")
        return
    thumb: pv.Image = pv.Image.thumbnail(sourcePath, width, size=pv.Size.DOWN)
    pv.Image.heifsave(thumb, targetPath, Q=quality, compression="av1", effort=effort)

def push_to_r2(pathData: tuple[Path, Path]) -> None:
    """
    Push source images and thumbnails to R2 via `boto3`
    """
    logger.info("Connecting to object storage...")
    aws_endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    s3 = boto3.client("s3", endpoint_url = aws_endpoint_url, region_name="auto")
    for src, thumb in pathData:
        try:
            s3.upload_file(src, os.getenv("S3_BUCKET_NAME"), src.name)
            s3.upload_file(thumb, os.getenv("S3_BUCKET_NAME"), thumb.name)
        except ClientError as e:
            logger.error(e)
    logger.info(f"Completed uploading {len(pathData)} images to R2.")

@lru_cache
def get_multi_insert_query(tableName: str, columns: tuple[str], rowCount: int) -> str:
    """
    Returns a multi-row insert SQL statement with `rowCount` rows
    """
    logger.debug(f"Generating {rowCount} row insert statement for table {tableName} with columns: {columns}")
    insertStr = f"INSERT INTO {tableName} ({", ".join(columns)}) VALUES "
    paramStr = ", ".join(["?" for _ in range(len(columns))])
    paramStr = "".join(["(", paramStr, ")"])
    paramStr = ",\n".join([paramStr for _ in range(rowCount)])
    return "".join([insertStr, paramStr, " ON CONFLICT DO NOTHING;"])

def batch_metadata(pathData: list[tuple[Path, Path]]):
    tableName = "photo"
    columns = ("filename", "thumbnail", "camera_model", "lens", "date_taken", "exposure_time", "focal_length", "f_stop", "iso")
    maxRows = BATCH_PARAM_LIMIT // len(columns)
    photoData = []
    batchedQueries = []
    for i, paths in enumerate(pathData):
        src, thumb = paths
        photoData.extend([src.name, thumb.name, "OLYMPUS XA2", "NULL", "NULL", "NULL", "NULL", "NULL", "NULL"])
        # If max params per query or final pair of path data reached
        if (not (i+1) % maxRows) or (i == len(pathData) - 1): 
            query = get_multi_insert_query(tableName, columns, maxRows if not (i+1) % maxRows else (i+1) % maxRows)
            batchedQueries.append({"sql": query, "params": photoData})
            photoData = []
    batch_d1(batchedQueries)

def batch_d1(batchedQueries: list[dict[str: str, str: list[str]]]) -> None:
    """
    Note that the D1/SQLite limit for bound parameters is 100.
    
    For a table with `c` columns, we can insert up to `r = 100 / c` rows per query.
    """
    d1Url = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv("CLOUDFLARE_ACCOUNT_ID")}/d1/database/{os.getenv("CLOUDFLARE_D1_ID")}/query"
    apiToken = os.getenv("CLOUDFLARE_D1_TOKEN")
    logger.debug(f"Attempting batch of {len(batchedQueries)} queries")
    try:
        res = requests.post(d1Url, 
                    headers= {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {apiToken}",
                    },
                    json={
                        "batch": batchedQueries
                    })
        logger.debug(f"HTTP {res.status_code}: {res.content.decode()}")
        res.raise_for_status()
        logger.info("Batch query successful.")
    except requests.exceptions.RequestException as e:
        logger.error(e)

def debug_sql(sqlQuery: str) -> str:
    return " ".join([sqlLine.strip() for sqlLine in sqlQuery.splitlines()])

def query_d1(sqlQuery: str):
    d1Url = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv("CLOUDFLARE_ACCOUNT_ID")}/d1/database/{os.getenv("CLOUDFLARE_D1_ID")}/query"
    apiToken = os.getenv("CLOUDFLARE_D1_TOKEN")
    try:
        logger.info(f"Querying D1 with SQL string: {debug_sql(sqlQuery)}")
        res = requests.post(d1Url, 
                    headers= {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {apiToken}",
                    },
                    json={
                        "sql": sqlQuery
                    })
        res.raise_for_status()
        logger.info(f"HTTP {res.status_code}: {res.content.decode()}")
    except requests.exceptions.RequestException as e:
        logger.error(e)

def create_photo_table():
    queryString = """CREATE TABLE IF NOT EXISTS photo (
    id INTEGER NOT NULL PRIMARY KEY ,
    filename TEXT NOT NULL UNIQUE,
    thumbnail TEXT NOT NULL UNIQUE,
    date_taken TEXT,
    lens TEXT,
    focal_length TEXT,
    f_stop TEXT,
    exposure_time TEXT,
    iso TEXT,
    camera_model TEXT);"""
    query_d1(queryString)

def create_collection_table():
    queryString = """CREATE TABLE IF NOT EXISTS collection (
    id INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL);"""
    query_d1(queryString)

def create_photo_collection_table():
    queryString = """CREATE TABLE IF NOT EXISTS photo_collection (
    photo_id INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,
    FOREIGN KEY (photo_id) REFERENCES photo(id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collection(id) ON DELETE CASCADE,
    PRIMARY KEY(photo_id, collection_id)
    );"""
    query_d1(queryString)

if __name__ == "__main__":
    main()