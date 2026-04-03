"""
Knowledge ingestion pipeline for Claude/Open Code.

Commands:
  pipeline ingest <repos.csv>   Clone repos, run gitingest, index into FAISS
  pipeline refresh               Pull latest, re-ingest, re-index
  pipeline serve                 Start the local-faiss MCP server
"""

import csv
import subprocess
import sys
from pathlib import Path

REPOS_DIR = Path("repos")
INGESTED_DIR = Path("ingested")
VECTOR_STORE_DIR = Path(".vector_store")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)


def _clone_repo(url: str) -> Path | None:
    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    dest = REPOS_DIR / repo_name

    if (dest / ".git").exists():
        print(f"  Already cloned: {repo_name}")
        return dest

    for branch in ("main", "master"):
        result = _run(
            ["git", "clone", "--single-branch", "--branch", branch, "--depth", "1", url, str(dest)],
            capture_output=True,
        )
        if result.returncode == 0:
            return dest

    print(f"  ERROR: Could not clone {url} (tried main/master)")
    return None


def _ingest_repo(repo_path: Path) -> Path:
    output = INGESTED_DIR / f"{repo_path.name}.txt"
    _run(["gitingest", str(repo_path), "-o", str(output)], check=True)
    return output


def _index_all() -> None:
    _run(["local-faiss", "index", str(INGESTED_DIR)], check=True)


def _load_csv(csv_path: str) -> list[str]:
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        return [row[0].strip() for row in reader if row and row[0].strip() and not row[0].startswith("#")]


def cmd_ingest(csv_path: str) -> None:
    REPOS_DIR.mkdir(exist_ok=True)
    INGESTED_DIR.mkdir(exist_ok=True)
    VECTOR_STORE_DIR.mkdir(exist_ok=True)

    urls = _load_csv(csv_path)
    if not urls:
        print("No URLs found in CSV.")
        return

    print(f"Processing {len(urls)} repo(s)...\n")
    for url in urls:
        print(f"[{url}]")
        repo = _clone_repo(url)
        if repo:
            _ingest_repo(repo)
        print()

    print("Indexing all ingested files into FAISS...")
    _index_all()
    print("\nDone. Run `pipeline serve` to start the MCP server.")


def cmd_refresh() -> None:
    if not REPOS_DIR.exists():
        print("No repos directory found. Run `pipeline ingest <repos.csv>` first.")
        sys.exit(1)

    repos = [r for r in REPOS_DIR.iterdir() if r.is_dir() and (r / ".git").exists()]
    if not repos:
        print("No cloned repos found.")
        return

    print(f"Refreshing {len(repos)} repo(s)...\n")
    for repo in repos:
        print(f"[{repo.name}]")
        _run(["git", "-C", str(repo), "pull", "--ff-only"], check=True)
        _ingest_repo(repo)
        print()

    print("Re-indexing all ingested files into FAISS...")
    _index_all()
    print("\nDone.")


def cmd_serve() -> None:
    if not VECTOR_STORE_DIR.exists():
        print("Vector store not found. Run `pipeline ingest <repos.csv>` first.")
        sys.exit(1)

    print(f"Starting local-faiss MCP server (index-dir: {VECTOR_STORE_DIR})...")
    _run(["local-faiss-mcp", "--index-dir", str(VECTOR_STORE_DIR)], check=True)


def main() -> None:
    args = sys.argv[1:]

    match args:
        case ["ingest", csv_path]:
            cmd_ingest(csv_path)
        case ["refresh"]:
            cmd_refresh()
        case ["serve"]:
            cmd_serve()
        case _:
            print(__doc__)
            sys.exit(1 if args else 0)


if __name__ == "__main__":
    main()
