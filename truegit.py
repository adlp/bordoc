from pathlib import Path
from contextlib import contextmanager
import os
import shutil
from typing import List, Dict, Any, Set, Optional

from dulwich.repo import Repo
from dulwich import porcelain
from dulwich.index import IndexEntry
from dulwich.objects import Commit, Blob, Tree


@contextmanager
def chdir(path: Path):
    old = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(old)


class TrueGit:
    """
    Minimal, robust wrapper around Dulwich for tests and simple operations.
    """

    def __init__(self, repo_path: str, default_branch: str = "main"):
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch

        repo_created = False

        # 1) Init repo if necessary
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            porcelain.init(str(self.repo_path))
            repo_created = True

        # Load repo
        self.repo = Repo(str(self.repo_path))

        master_ref = b"refs/heads/master"
        main_ref = f"refs/heads/{self.default_branch}".encode()

        # 2) If master exists but main not, create main from master
        if master_ref in self.repo.refs and main_ref not in self.repo.refs:
            self.repo.refs[main_ref] = self.repo.refs[master_ref]

        # 3) Ensure HEAD points to default branch, but do not overwrite existing HEAD
        head_file = self.repo_path / ".git" / "HEAD"
        if not head_file.exists():
            head_file.write_text(f"ref: refs/heads/{self.default_branch}\n", encoding="utf-8")
            # reload repo so Dulwich sees the new HEAD
            self.repo = Repo(str(self.repo_path))

        # 4) If repo freshly created, create an initial commit
        if repo_created:
            init_file = self.repo_path / ".gitignore"
            init_file.write_text("# initial\n", encoding="utf-8")
            with chdir(self.repo_path):
                porcelain.add(".", paths=[".gitignore"])
                porcelain.commit(
                    ".",
                    message="First",
                    author="truegit <local>",
                    committer="truegit <local>",
                )
            # reload repo to reflect new refs/objects
            self.repo = Repo(str(self.repo_path))

    # -------------------------
    # Helpers
    # -------------------------
    def _git_dir(self) -> Path:
        return (self.repo_path / ".git").resolve()

    def _is_in_git(self, p: Path) -> bool:
        try:
            git_dir = self._git_dir()
            return git_dir == p.resolve() or git_dir in p.resolve().parents
        except Exception:
            return False

    # -------------------------
    # Branch / refs utilities
    # -------------------------
    def current_branch(self) -> str:
        """Return current branch name or 'HEAD' if detached/unborn."""
        head_file = self.repo_path / ".git" / "HEAD"
        try:
            content = head_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return "HEAD"
        if content.startswith("ref:"):
            return content.split("/")[-1]
        return "HEAD"

    def branches(self) -> List[str]:
        """List local branch names."""
        heads = []
        for ref in self.repo.refs.keys():
            if ref.startswith(b"refs/heads/"):
                heads.append(ref.decode().split("/")[-1])
        return sorted(heads)

    # -------------------------
    # Log / status
    # -------------------------
    def log(self, branch: Optional[str] = None, max_entries: int = 50) -> List[Dict[str, Any]]:
        branch = branch or self.current_branch()
        ref = f"refs/heads/{branch}".encode()
        if ref not in self.repo.refs:
            raise ValueError(f"La branche {branch} n'existe pas")
        head_sha = self.repo.refs[ref]
        walker = self.repo.get_walker(head_sha)
        commits = []
        for entry in walker:
            commit = entry.commit
            commits.append(
                {
                    "sha": commit.id.decode() if isinstance(commit.id, bytes) else str(commit.id),
                    "author": commit.author.decode() if commit.author else "",
                    "message": commit.message.decode().strip() if commit.message else "",
                    "time": commit.commit_time,
                }
            )
        return commits

    def status(self):
        """Return porcelain.status output (staged/unstaged)."""
        with chdir(self.repo_path):
            return porcelain.status(".")

    # -------------------------
    # Branch operations
    # -------------------------
    def create_branch(self, branch: str):
        """
        Create a branch from the commit pointed by HEAD.
        If HEAD points to a commit, branch -> that SHA.
        If HEAD is unborn but points to a symbolic ref, create a symbolic ref.
        Always reload self.repo after modification.
        """
        ref = f"refs/heads/{branch}".encode()
    
        # Try to read the ref that HEAD points to (e.g. b"refs/heads/main")
        try:
            head_ref = self.repo.refs.read_ref(b"HEAD")
        except Exception:
            head_ref = None
    
        head_sha = None
        if head_ref is not None:
            try:
                head_sha = self.repo.refs[head_ref]
            except KeyError:
                head_sha = None
    
        if head_sha:
            # Normal case: HEAD points to a commit SHA
            self.repo.refs[ref] = head_sha
        else:
            # HEAD unborn: create a symbolic ref pointing to the same ref as HEAD (if any)
            if head_ref is not None:
                try:
                    self.repo.refs.set_symbolic_ref(ref, head_ref)
                except Exception:
                    # Fallback: create the loose ref file empty (rare)
                    ref_path = self.repo_path / ".git" / "refs" / "heads" / branch
                    ref_path.parent.mkdir(parents=True, exist_ok=True)
                    ref_path.write_text("", encoding="utf-8")
            else:
                # No head_ref readable: create an empty loose ref file (rare)
                ref_path = self.repo_path / ".git" / "refs" / "heads" / branch
                ref_path.parent.mkdir(parents=True, exist_ok=True)
                ref_path.write_text("", encoding="utf-8")
    
        # IMPORTANT: reload repo so Dulwich sees the new ref immediately
        self.repo = Repo(str(self.repo_path))
    
    
    def delete_branch(self, branch: str):
        ref = f"refs/heads/{branch}".encode()
        if ref in self.repo.refs:
            del self.repo.refs[ref]

    # -------------------------
    # File operations
    # -------------------------
    def read(self, filepath: str, branch: Optional[str] = None) -> str:
        """Read a file from a given branch (or current branch)."""
        branch = branch or self.current_branch()
        ref = f"refs/heads/{branch}".encode()
        if ref not in self.repo.refs:
            raise ValueError(f"La branche {branch} n'existe pas")
        commit_sha = self.repo.refs[ref]
        if commit_sha is None:
            raise FileNotFoundError(f"Branch {branch} has no commit")
        commit = self.repo[commit_sha]
        tree = self.repo[commit.tree]
        parts = filepath.strip("/").split("/")
        obj = tree
        for part in parts:
            key = part.encode()
            mode, sha = obj[key]
            obj = self.repo[sha]
        return obj.data.decode()

    def add(self, filepath: str):
        """Stage a file (git add)."""
        with chdir(self.repo_path):
            porcelain.add(".", paths=[filepath])

    def rm(self, filepath: str):
        """Remove a file from FS and stage its deletion."""
        full_path = (self.repo_path / filepath)
        if full_path.exists():
            full_path.unlink()
        with chdir(self.repo_path):
            porcelain.add(".", paths=[filepath])

    def commit(self, message: str, author: str = "truegit <local>") -> str:
        """
        Create a commit from the current index.
        porcelain.commit will update the ref pointed by HEAD.
        """
        with chdir(self.repo_path):
            commit_id = porcelain.commit(
                ".",
                message=message,
                author=author,
                committer=author,
            )
        # reload repo to keep Dulwich cache consistent
        self.repo = Repo(str(self.repo_path))
        sha = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
        return sha

    def write(self, filepath: str, content: str, branch: Optional[str] = None, message: str = "update", author: str = "truegit <local>") -> str:
        """
        Write a file, add and commit it.
        If branch is provided, ensure the write happens on that branch.
        """
        filepath = filepath.strip("/")
        full_path = (self.repo_path / filepath)

        # If branch specified, ensure it exists and checkout it
        if branch is not None:
            ref = f"refs/heads/{branch}".encode()
            if ref not in self.repo.refs:
                self.create_branch(branch)
            if self.current_branch() != branch:
                self.checkout(branch)

        # Write file to FS
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

        # add + commit
        with chdir(self.repo_path):
            porcelain.add(".", paths=[filepath])
            commit_id = porcelain.commit(
                ".",
                message=message,
                author=author,
                committer=author,
            )

        # reload repo to keep Dulwich cache consistent
        self.repo = Repo(str(self.repo_path))
        sha = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
        return sha

    # -------------------------
    # Robust checkout
    # -------------------------
    def checkout(self, branch: str):
        """
        Robust checkout:
        - reload repo first to ensure refs are fresh
        - update HEAD, reload repo again
        - compute expected tree paths
        - remove any worktree files not in expected set (never touch .git)
        - recreate files from the commit tree
        - rebuild the index to match the tree
        - final verification
        """
        ref = f"refs/heads/{branch}".encode()
    
        # --- Ensure we have the freshest view of refs (fixes race with create_branch)
        self.repo = Repo(str(self.repo_path))
    
        # If the ref is still missing, try a filesystem fallback (packed-refs or direct file)
        if ref not in self.repo.refs:
            # reload once more (defensive)
            self.repo = Repo(str(self.repo_path))
            if ref not in self.repo.refs:
                # fallback: check on-disk refs (loose refs)
                ref_path = self.repo_path / ".git" / "refs" / "heads" / branch
                if not ref_path.exists():
                    # final fallback: check packed-refs
                    packed = self.repo_path / ".git" / "packed-refs"
                    if not packed.exists():
                        raise ValueError(f"La branche {branch} n'existe pas")
                    # if packed exists but branch not found, still raise
                    # (we could parse packed-refs here if needed)
                    raise ValueError(f"La branche {branch} n'existe pas")
    
        # 0) HEAD -> branch (first) and reload repo to invalidate Dulwich cache
        head_file = self.repo_path / ".git" / "HEAD"
        head_file.write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
        self.repo = Repo(str(self.repo_path))
        print("DEBUG: repo.refs keys:", sorted([r.decode() for r in self.repo.refs.keys() if r.startswith(b"refs/heads/")]))
    
        # 1) Read commit and tree (handle unborn branch)
        commit_sha = None
        try:
            commit_sha = self.repo.refs[ref]
            print("DEBUG: commit_sha for", branch, "=", commit_sha)
        except KeyError:
            print("DEBUG: no commit sha for", branch)
            commit_sha = None
    
        if commit_sha is None:
            tree = None
            expected: Set[str] = set()
        else:
            commit = self.repo[commit_sha]
            tree = self.repo[commit.tree]
    
            # 2) Collect expected file paths from the tree (posix-style relative)
            def collect_tree_paths(tree_obj, base="") -> Set[str]:
                paths = set()
                for name in tree_obj:
                    mode, sha = tree_obj[name]
                    obj = self.repo[sha]
                    name_s = name.decode() if isinstance(name, bytes) else name
                    full = name_s if base == "" else f"{base}/{name_s}"
                    if obj.type_name == b"tree":
                        paths |= collect_tree_paths(obj, full)
                    else:
                        paths.add(full)
                return paths
    
            expected = collect_tree_paths(tree)
    
        # debug
        print("DEBUG: expected paths:", sorted(expected))
    
        git_dir = (self.repo_path / ".git").resolve()
    
        def is_in_git(path: Path) -> bool:
            try:
                return git_dir == path.resolve() or git_dir in path.resolve().parents
            except Exception:
                return False
    
        # 3) Remove any file in worktree not in expected (skip .git)
        for root, dirs, files in os.walk(self.repo_path, topdown=False):
            root_path = Path(root)
            if is_in_git(root_path):
                continue
    
            for f in files:
                full_path = root_path / f
                if is_in_git(full_path):
                    continue
                rel = os.path.relpath(full_path, self.repo_path).replace(os.sep, "/")
                if rel not in expected:
                    try:
                        if full_path.is_symlink() or full_path.is_file():
                            full_path.unlink()
                            print("DEBUG: removed file", rel)
                        else:
                            full_path.unlink()
                            print("DEBUG: removed (fallback) file", rel)
                    except Exception as e:
                        print("WARN: failed to remove file", rel, ":", e)
    
            for d in dirs:
                dpath = root_path / d
                if is_in_git(dpath):
                    continue
                rel_dir = os.path.relpath(dpath, self.repo_path).replace(os.sep, "/")
                has_expected_under = any(p == rel_dir or p.startswith(rel_dir + "/") for p in expected)
                if not has_expected_under:
                    try:
                        dpath.rmdir()
                        print("DEBUG: removed empty dir", rel_dir)
                    except OSError:
                        try:
                            shutil.rmtree(dpath)
                            print("DEBUG: rmtree removed dir", rel_dir)
                        except Exception as e:
                            print("WARN: failed to rmtree", rel_dir, ":", e)
    
        # 4) Recreate expected files from the tree
        if tree is not None:
            def checkout_tree(tree_obj, base_path: Path):
                for name in tree_obj:
                    mode, sha = tree_obj[name]
                    obj = self.repo[sha]
                    name_str = name.decode() if isinstance(name, bytes) else name
                    path = base_path / name_str
                    if is_in_git(path):
                        continue
                    if obj.type_name == b"tree":
                        path.mkdir(parents=True, exist_ok=True)
                        checkout_tree(obj, path)
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(obj.data)
                        print("DEBUG: wrote file", str(path.relative_to(self.repo_path)))
    
            checkout_tree(tree, self.repo_path)
    
        # 5) Rebuild the index from the tree
        index = self.repo.open_index()
        index.clear()
    
        def add_tree_to_index(tree_obj, base=b""):
            for name in tree_obj:
                mode, sha = tree_obj[name]
                obj = self.repo[sha]
                full = name if base == b"" else base + b"/" + name
                if obj.type_name == b"tree":
                    add_tree_to_index(obj, full)
                else:
                    entry = IndexEntry(
                        0, 0, 0, 0, mode,
                        0, 0,
                        len(obj.data),
                        sha,
                        0
                    )
                    index[full] = entry
    
        if tree is not None:
            add_tree_to_index(tree)
        index.write()
    
        # 6) Final verification: no unexpected files remain
        remaining = []
        for root, dirs, files in os.walk(self.repo_path):
            root_path = Path(root)
            if is_in_git(root_path):
                continue
            for f in files:
                rel = os.path.relpath(root_path / f, self.repo_path).replace(os.sep, "/")
                if rel not in expected:
                    remaining.append(rel)
    
        if remaining:
            print("ERROR: remaining unexpected files after checkout:", remaining)
            raise RuntimeError(f"Checkout incomplete, remaining files: {remaining}")
    
        print("DEBUG: checkout complete, expected files present and no unexpected files remain.")
    
