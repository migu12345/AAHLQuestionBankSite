"""Check the files and routes needed by the deployed question banks."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import REQUIRED_JSON_FILES, REQUIRED_LOCAL_ASSETS, app  # noqa: E402


class HomeLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        if href.endswith(".html") and not href.startswith(("http:", "https:")):
            self.paths.add("/" + href.lstrip("/"))


def routes():
    links = HomeLinks()
    links.feed((ROOT / "src" / "index.html").read_text(encoding="utf-8"))
    return sorted({"/", "/health", *links.paths, *REQUIRED_JSON_FILES, *REQUIRED_LOCAL_ASSETS})


def docker_sources():
    sources = set()
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0].upper() == "COPY":
            sources.update("/" + source for source in parts[1:-1])
    return sources


def check_local(paths):
    missing_copies = sorted(set((*REQUIRED_JSON_FILES, *REQUIRED_LOCAL_ASSETS)) - docker_sources())
    if missing_copies:
        print("Dockerfile is missing:")
        for path in missing_copies:
            print("  " + path)
        return 1

    client = app.test_client()
    failures = [(path, response.status_code) for path in paths if (response := client.head(path)).status_code != 200]
    if failures:
        for path, status in failures:
            print(f"FAIL {status} {path}")
        return 1
    print(f"OK: {len(paths)} local routes; all required data files are copied into Docker")
    return 0


def check_remote(base_url, paths, timeout):
    failures = []
    for path in paths:
        request = Request(base_url.rstrip("/") + path, method="HEAD")
        for attempt in range(2):
            try:
                with urlopen(request, timeout=timeout) as response:
                    status = response.status
                break
            except HTTPError as error:
                status = error.code
                break
            except (URLError, TimeoutError) as error:
                if attempt == 1:
                    failures.append((path, str(getattr(error, "reason", error))))
        else:
            continue
        if status != 200:
            failures.append((path, status))
    if failures:
        for path, status in failures:
            print(f"FAIL {status} {path}")
        return 1
    print(f"OK: {len(paths)} live routes at {base_url.rstrip('/')}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Check a deployed site instead of the local Flask app")
    parser.add_argument("--timeout", type=float, default=30, help="Seconds per live request")
    args = parser.parse_args()
    paths = routes()
    return check_remote(args.base_url, paths, args.timeout) if args.base_url else check_local(paths)


if __name__ == "__main__":
    raise SystemExit(main())
