# gallery-utils

A collection of utilities for managing and displaying image galleries. Used for my blog and photo gallery.

## tools
- `thumbnail.py`: A script to generate thumbnails for images in a specified directory.

## usage

setup: 
```
git clone https://github.com/LordExodius/gallery-utils.git
cd gallery-utils
pip install -r requirements.txt
```

### thumbnail.py 
Usage: Run `python ./thumbnail.py [--help] [-w, --width WIDTH] [-q, --quality QUALITY] SOURCE_PATH`

- `SOURCE_PATH`: Path to the directory containing images.
- `-w, --width WIDTH`: Optional. Width of the generated thumbnails in pixels. Default is 1000px.
- `-q, --quality QUALITY`: Optional. Quality of the generated thumbnails (1-100). Default is 75.

Thumbnails are saved in a `thumbnails` subdirectory within the source directory.