"""
Knowledge ingestion pipeline for Claude/Open Code.

Commands:
  pipeline deps <project_path> [--ingest]
                                Scan project dependencies, resolve to GitHub
                                URLs, append to repos.csv
  pipeline ingest <repos.csv>   Clone repos, run gitingest, index into FAISS
  pipeline refresh               Pull latest, re-ingest, re-index
  pipeline serve                 Start the local-faiss MCP server
"""

import csv
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import httpx

REPOS_DIR = Path("repos")
INGESTED_DIR = Path("ingested")
VECTOR_STORE_DIR = Path(".vector_store")
REPOS_CSV = Path("repos.csv")

# ── helpers ──────────────────────────────────────────────────────────────────

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


def _load_csv(csv_path: str | Path) -> list[str]:
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        return [row[0].strip() for row in reader if row and row[0].strip() and not row[0].startswith("#")]


# ── deps: parsing ────────────────────────────────────────────────────────────

_PKG_NAME_RE = re.compile(r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)")


def _strip_pkg_name(spec: str) -> str:
    """Extract bare package name from a dependency specifier."""
    m = _PKG_NAME_RE.match(spec.strip())
    return m.group(1) if m else ""


def _parse_python_deps(project: Path) -> list[tuple[str, str]]:
    """Return [(name, ecosystem), ...] for Python deps."""
    packages: list[tuple[str, str]] = []

    pyproject = project / "pyproject.toml"
    if pyproject.exists():
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        raw = data.get("project", {}).get("dependencies", [])
        for spec in raw:
            name = _strip_pkg_name(spec)
            if name:
                packages.append((name, "pypi"))

    requirements = project / "requirements.txt"
    if requirements.exists():
        for line in requirements.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            name = _strip_pkg_name(line)
            if name:
                packages.append((name, "pypi"))

    return packages


def _parse_js_deps(project: Path) -> list[tuple[str, str]]:
    """Return [(name, ecosystem), ...] for JS deps."""
    pkg_json = project / "package.json"
    if not pkg_json.exists():
        return []

    data = json.loads(pkg_json.read_text())
    names = list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())
    return [(name, "npm") for name in names]


# ── deps: GitHub URL resolution ───────────────────────────────────────────────

_GH_RE = re.compile(r"github\.com[/:]([^/]+/[^/\s#?\.]+)")


def _extract_github_url(raw: str) -> str | None:
    """Pull a clean https://github.com/owner/repo URL from a raw string."""
    m = _GH_RE.search(raw)
    if not m:
        return None
    slug = m.group(1).removesuffix(".git")
    return f"https://github.com/{slug}"


def _resolve_pypi(client: httpx.Client, name: str) -> str | None:
    try:
        r = client.get(f"https://pypi.org/pypi/{name}/json", timeout=10)
        if r.status_code != 200:
            return None
        info = r.json()["info"]
        project_urls: dict = info.get("project_urls") or {}
        for key in ("Source", "Repository", "Source Code", "Code", "Homepage"):
            url = project_urls.get(key, "")
            gh = _extract_github_url(url)
            if gh:
                return gh
        return _extract_github_url(info.get("home_page") or "")
    except Exception:
        return None


def _resolve_npm(client: httpx.Client, name: str) -> str | None:
    try:
        r = client.get(f"https://registry.npmjs.org/{name}/latest", timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        repo = data.get("repository", {})
        repo_url = repo.get("url", "") if isinstance(repo, dict) else str(repo)
        gh = _extract_github_url(repo_url) or _extract_github_url(data.get("homepage", ""))
        return gh
    except Exception:
        return None


# ── deps command ──────────────────────────────────────────────────────────────

def cmd_deps(project_path: str, ingest: bool = False) -> None:
    project = Path(project_path).resolve()
    if not project.exists():
        print(f"ERROR: {project} does not exist.")
        sys.exit(1)

    # detect and parse
    packages: list[tuple[str, str]] = []
    if (project / "pyproject.toml").exists() or (project / "requirements.txt").exists():
        py = _parse_python_deps(project)
        print(f"Found {len(py)} Python dep(s) in {project_path}")
        packages += py
    if (project / "package.json").exists():
        js = _parse_js_deps(project)
        print(f"Found {len(js)} JS dep(s) in {project_path}")
        packages += js

    if not packages:
        print("No dependencies found (checked pyproject.toml, requirements.txt, package.json).")
        return

    # deduplicate by name
    seen_names: set[str] = set()
    unique: list[tuple[str, str]] = []
    for name, eco in packages:
        if name.lower() not in seen_names:
            seen_names.add(name.lower())
            unique.append((name, eco))

    print(f"\nResolving {len(unique)} package(s) to GitHub URLs...\n")

    # load existing URLs to avoid duplication
    existing: set[str] = set()
    if REPOS_CSV.exists():
        existing = {u.lower() for u in _load_csv(REPOS_CSV)}

    resolved: list[str] = []
    skipped: list[str] = []

    with httpx.Client() as client:
        for name, eco in unique:
            url = _resolve_pypi(client, name) if eco == "pypi" else _resolve_npm(client, name)
            if url:
                if url.lower() in existing:
                    print(f"  skip  {name} → {url} (already in repos.csv)")
                else:
                    print(f"  found {name} → {url}")
                    resolved.append(url)
                    existing.add(url.lower())
            else:
                skipped.append(name)
                print(f"  miss  {name} (no GitHub URL found)")

    if resolved:
        with open(REPOS_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            for url in resolved:
                writer.writerow([url])
        print(f"\nAdded {len(resolved)} URL(s) to {REPOS_CSV}.")
    else:
        print("\nNo new URLs to add.")

    if skipped:
        print(f"Skipped {len(skipped)} package(s) with no GitHub URL: {', '.join(skipped)}")

    if ingest and resolved:
        print()
        cmd_ingest(str(REPOS_CSV))


# ── ingest / refresh / serve ──────────────────────────────────────────────────

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


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    match args:
        case ["deps", project_path]:
            cmd_deps(project_path)
        case ["deps", project_path, "--ingest"]:
            cmd_deps(project_path, ingest=True)
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
