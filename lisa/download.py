"""Downloads model files on first use."""

import urllib.request


def download(url, path):
    """Download `url` to `path` unless it already exists, via a temporary file so a broken download isn't kept.

    :param url: Source URL
    :param path: Destination file
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".part")
    print(f"Downloading {path.name} ...", flush=True)
    urllib.request.urlretrieve(url, temp_path)
    temp_path.replace(path)
