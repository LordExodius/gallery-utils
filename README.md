# gallery-utils

A collection of utilities for managing image galleries. Used for my blog and photo gallery.

## tools
- `thumbnail.py`: A script to generate thumbnails for images. 
    - This utility creates `.avif` thumbnails, uploads photos to Cloudflare R2, and metadata to Cloudflare D1 for gallery access. You can also run it in offline mode to just generate thumbnails without uploading.
    - Any S3-compatible storage can be used by setting the appropriate environment variables in a `.env` file. See `thumbnail.py` for details.
    - Cloudflare D1 is used to store metadata about the images and collections. Ensure you have the necessary database and tables set up before using the upload features.
## usage

general setup: 
```
git clone https://github.com/LordExodius/gallery-utils.git
cd gallery-utils
pip install -r requirements.txt
```

### thumbnail.py 

#### Prerequisites:
- In order to use any of the upload features, you need to have a Cloudflare R2 bucket (or other S3-compatible storage) and a Cloudflare D1 database set up.
- You may ignore the upload features and just use the thumbnail generation locally with the `-oo` or `--offlineOnly` flag.
- Set the following environment variables in a `.env` file in the project root:
    - `AWS_ACCESS_KEY_ID`
    - `AWS_SECRET_ACCESS_KEY`
    - `AWS_ENDPOINT_URL`
    - `S3_BUCKET_NAME`

#### Usage:
Run `python ./thumbnail.py SOURCE_PATH`

#### Arguments:
All arguments other than `SOURCE_PATH` are optional.
| Parameter | Description |
|-----------|-------------|
| `SOURCE_PATH` | Path to the directory containing images OR path to a single image.
| `-w, --width WIDTH` | Width of the generated thumbnails in pixels. Default is 1000px.
| `-q, --quality QUALITY` | Quality of the generated thumbnails (1-100). Default is 75.
| `-e, --effort EFFORT` | CPU effort spent improving compression (0: fastest, 9: slowest). Default is 4.
| `-c, --collection COLLECTION` | Collection(s) to add photos to (use ; to delimit collections).
| `-o, --overwrite` | Disable smart thumbnail generation and overwrite stored images. This will also cause all images to be re-uploaded.
| `-oo, --offlineOnly` | Disable file uploads and only generate thumbnails locally.
| `-uo, --uploadOnly` | Skip thumbnail generation and only upload to D1 and R2.

Thumbnails are saved in a `thumbnails` subdirectory within the source directory.