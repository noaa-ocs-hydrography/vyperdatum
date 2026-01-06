import os
import shutil
import time
from typing import TypedDict
import logging
import requests
from tqdm.auto import tqdm
import zipfile
from vyperdatum.enums import DATUM_DOI, ASSETS


logger = logging.getLogger("root_logger")


def datums_missing(datums_dir: str):
    """
    Rerturn True if the datum directory in the assets dir is empty or missing.
    """
    return not (os.path.isdir(datums_dir) and len(os.listdir(datums_dir)) > 0)


class DOI(TypedDict):
    url: str
    dir_name: str

def download_datums(doi: DOI):
    """
    Download datum files, unzip and copy them to the assets directory.
    """
    url = doi["url"]
    logger.info(f"Downloading datum and proj.db files from: {url}")
    resp = requests.get(url, stream=True)
    total = int(resp.headers.get("content-length", 0))
    zip_name = f"{ASSETS.DIR.value}/datums.zip"
    chunk_size = 1024
    with open(zip_name, "wb") as file, tqdm(
        desc=zip_name,
        total=total,
        unit="iB",
        unit_scale=True,
        unit_divisor=chunk_size,
    ) as bar:
        for data in resp.iter_content(chunk_size=chunk_size):
            size = file.write(data)
            bar.update(size)
    logger.info(f"Unzipping {zip_name}")
    with zipfile.ZipFile(zip_name, "r") as zip_ref:
        zip_ref.extractall(ASSETS.DIR.value)
    os.remove(zip_name)
    time.sleep(2)
    try:
        src_dir = f"{ASSETS.DIR.value}/{doi['dir_name']}"
        dst_dir = f"{ASSETS.DIR.value}/datums"
        shutil.move(src=src_dir, dst=dst_dir)
    except Exception as e:
        logger.exception(f"{e}\nUnable to rename a directory due to potential permission issue."
                         f" Please rename {src_dir} to {dst_dir} manually and run again.")
    return
