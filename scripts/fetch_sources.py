"""Fetch the exact 300 upstream files and verify their SHA-256 hashes."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen, Request
from urllib.parse import quote
import csv, json, hashlib, argparse, shutil, time

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache",
        type=Path,
        help="Optional previously downloaded data directory; hashes are always checked.",
    )
    args = parser.parse_args()
    sources = {
        s["source"]: s
        for s in json.loads((ROOT / "data/source_manifest.json").read_text())["sources"]
    }
    rows = list(csv.DictReader((ROOT / "data/source_file_manifest.csv").open()))

    def fetch(r):
        rel = Path(r["relative_path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        dest = ROOT / "data" / r["source"] / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and sha(dest) == r["sha256"]:
            return
        if args.cache:
            cached = args.cache / r["source"] / rel
            if cached.exists() and sha(cached) == r["sha256"]:
                shutil.copyfile(cached, dest)
                return
        src = sources[r["source"]]
        repo = src["repo_url"].split("github.com/", 1)[1]
        url = (
            "https://raw.githubusercontent.com/"
            + repo
            + "/"
            + src["commit"]
            + "/"
            + quote(rel.as_posix(), safe="/")
        )
        tmp = dest.with_name(dest.name + ".download")
        for attempt in range(3):
            try:
                with (
                    urlopen(
                        Request(
                            url,
                            headers={"User-Agent": "quantum-artifact-reproduction/1.0"},
                        ),
                        timeout=90,
                    ) as response,
                    tmp.open("wb") as f,
                ):
                    shutil.copyfileobj(response, f, 1024 * 1024)
                assert sha(tmp) == r["sha256"], (
                    "Upstream hash mismatch: " + rel.as_posix()
                )
                tmp.replace(dest)
                return
            except Exception:
                tmp.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(fetch, rows))
    print(f"Verified {len(rows)} upstream files against pinned source hashes.")


if __name__ == "__main__":
    main()
