from pathlib import Path
from contextlib import contextmanager
import os
import shutil
from typing import List, Dict, Any, Set, Optional

from dulwich.repo import Repo
from dulwich import porcelain
from dulwich.index import IndexEntry
from dulwich.objects import Commit


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
    Robust minimal wrapper around Dulwich for tests.
    Use debug=True to see internal debug prints.
    """

    def __init__(self, repo_path: str, default_branch: str = "main", debug: bool = False):
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch
        self.debug = debug

        repo_created = False

        # Init repo if necessary
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            porcelain.init(str(self.repo_path))
            repo_created = True

        # Load repo
        self.repo = Repo(str(self.repo_path))

        master_ref = b"refs/heads/master"
        main_ref = f"refs/heads/{self.default_branch}".encode()

        # If master exists but main not, create main from master
        if master_ref in self.repo.refs and main_ref not in self.repo.refs:
            self.repo.refs[main_ref] = self.repo.refs[master_ref]

        # Ensure HEAD points to default branch if HEAD file missing
        head_file = self.repo_path / ".git" / "HEAD"
        if not head_file.exists():
            head_file.write_text(f"ref: refs/heads/{self.default_branch}\n", encoding="utf-8")
            self.repo = Repo(str(self.repo_path))

        # If freshly created, create an initial commit
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

    def _dbg(self, *args):
        if self.debug:
            print("DEBUG:", *args)

    def _resolve_ref_to_sha(self, ref_name: bytes) -> Optional[bytes]:
        """
        Résout une ref (ex: b'refs/heads/feature') en SHA si possible.
        Suit les symbolic refs, vérifie loose refs et packed-refs.
        Retourne None si aucune SHA trouvée.
        """
        # 1) tentative directe via dulwich cache
        try:
            sha = self.repo.refs[ref_name]
            if sha:
                return sha
        except Exception:
            pass
    
        # 2) si c'est une symbolic ref, read_ref renvoie la cible
        try:
            target = self.repo.refs.read_ref(ref_name)
            try:
                sha = self.repo.refs[target]
                if sha:
                    return sha
            except Exception:
                pass
        except Exception:
            pass
    
        # 3) loose ref file fallback
        try:
            parts = ref_name.decode().split("/")
            ref_path = self.repo_path / ".git" / "refs" / "/".join(parts[2:])
            if ref_path.exists():
                txt = ref_path.read_text().strip()
                if txt:
                    return txt.encode()
        except Exception:
            pass
    
        # 4) packed-refs fallback (simple parse)
        packed = self.repo_path / ".git" / "packed-refs"
        if packed.exists():
            for line in packed.read_text().splitlines():
                if line.startswith("#") or line.strip() == "":
                    continue
                if " " in line:
                    sha_hex, name = line.split(" ", 1)
                    if name.strip() == ref_name.decode():
                        return sha_hex.encode()
    
        return None
    
    # -------------------------
    # Branch / refs utilities
    # -------------------------
    def current_branch(self) -> str:
        head_file = self.repo_path / ".git" / "HEAD"
        try:
            content = head_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return "HEAD"
        if content.startswith("ref:"):
            return content.split("/")[-1]
        return "HEAD"

    def branches(self) -> List[str]:
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
        with chdir(self.repo_path):
            return porcelain.status(".")

    # -------------------------
    # Branch operations
    # -------------------------
    def create_branch(self, branch: str):
        """
        Create a branch from the commit pointed by HEAD.
        If HEAD points to a commit, branch -> that SHA.
        If HEAD is unborn, create a symbolic ref pointing to the same ref as HEAD (normalized).
        Always reload self.repo after modification.
        """
        ref = f"refs/heads/{branch}".encode()
    
        # Try to read the ref that HEAD points to (may return b'ref: refs/heads/main' or b'refs/heads/main')
        try:
            raw_head_ref = self.repo.refs.read_ref(b"HEAD")
        except Exception:
            raw_head_ref = None
    
        # Normalize: if raw_head_ref starts with b"ref:" strip it
        head_ref = None
        if raw_head_ref is not None:
            if isinstance(raw_head_ref, bytes) and raw_head_ref.startswith(b"ref:"):
                # e.g. b"ref: refs/heads/main" -> b"refs/heads/main"
                head_ref = raw_head_ref.split(b":", 1)[1].strip()
            else:
                head_ref = raw_head_ref
    
        # Try to resolve a SHA for the head_ref
        head_sha = None
        if head_ref is not None:
            try:
                head_sha = self.repo.refs[head_ref]
            except Exception:
                head_sha = None
    
        if head_sha:
            # HEAD points to a commit SHA: create branch pointing to that SHA
            self.repo.refs[ref] = head_sha
            self._dbg("create_branch:", branch, "->", head_sha)
        else:
            # HEAD unborn: create a symbolic ref to the same ref as HEAD if we have a normalized head_ref
            if head_ref is not None:
                try:
                    self.repo.refs.set_symbolic_ref(ref, head_ref)
                    self._dbg("create_branch symbolic:", branch, "->", head_ref)
                except Exception as e:
                    # fallback: do not create an empty ref file; leave branch absent
                    self._dbg("create_branch: failed to set_symbolic_ref, not creating branch file:", e)
                    return
            else:
                # No head_ref readable: do nothing (do not create empty ref)
                self._dbg("create_branch: no head_ref, not creating branch")
                return
    
        # reload repo so Dulwich sees the new ref immediately
        self.repo = Repo(str(self.repo_path))
    
    def delete_branch(self, branch: str):
        ref = f"refs/heads/{branch}".encode()
        if ref in self.repo.refs:
            del self.repo.refs[ref]
            self.repo = Repo(str(self.repo_path))

    # -------------------------
    # File operations
    # -------------------------
    def read(self, filepath: str, branch: Optional[str] = None) -> str:
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
        with chdir(self.repo_path):
            porcelain.add(".", paths=[filepath])

    def rm(self, filepath: str):
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
        self._dbg("commit:", sha, "message:", message)
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
        self._dbg("write commit:", sha, "file:", filepath)
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

        # Ensure freshest view of refs
        self.repo = Repo(str(self.repo_path))

        # If ref missing, try reload and fallback to on-disk check
        if ref not in self.repo.refs:
            self.repo = Repo(str(self.repo_path))
            if ref not in self.repo.refs:
                ref_path = self.repo_path / ".git" / "refs" / "heads" / branch
                if not ref_path.exists():
                    packed = self.repo_path / ".git" / "packed-refs"
                    if not packed.exists():
                        raise ValueError(f"La branche {branch} n'existe pas")
                    # If packed exists but branch not found, raise (parsing packed-refs optional)
                    raise ValueError(f"La branche {branch} n'existe pas")

        # 0) HEAD -> branch (first) and reload repo to invalidate Dulwich cache
        head_file = self.repo_path / ".git" / "HEAD"
        head_file.write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
        self.repo = Repo(str(self.repo_path))

#        # 1) Read commit and tree (handle unborn branch)
#        commit_sha = None
#        try:
#            commit_sha = self.repo.refs[ref]
#        except KeyError:
#            commit_sha = None
# après self.repo = Repo(str(self.repo_path))
        commit_sha = self._resolve_ref_to_sha(ref)
        if commit_sha is None:
            tree = None
            expected = set()
        else:
            commit = self.repo[commit_sha]
            tree = self.repo[commit.tree]
            # ensuite collect_tree_paths comme avant

            # collect expected file paths
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

        self._dbg("expected paths:", sorted(expected))

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
                            self._dbg("removed file", rel)
                        else:
                            full_path.unlink()
                            self._dbg("removed (fallback) file", rel)
                    except Exception as e:
                        self._dbg("WARN: failed to remove file", rel, ":", e)

            for d in dirs:
                dpath = root_path / d
                if is_in_git(dpath):
                    continue
                rel_dir = os.path.relpath(dpath, self.repo_path).replace(os.sep, "/")
                has_expected_under = any(p == rel_dir or p.startswith(rel_dir + "/") for p in expected)
                if not has_expected_under:
                    try:
                        dpath.rmdir()
                        self._dbg("removed empty dir", rel_dir)
                    except OSError:
                        try:
                            shutil.rmtree(dpath)
                            self._dbg("rmtree removed dir", rel_dir)
                        except Exception as e:
                            self._dbg("WARN: failed to rmtree", rel_dir, ":", e)

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
                        self._dbg("wrote file", str(path.relative_to(self.repo_path)))

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
            self._dbg("ERROR: remaining unexpected files after checkout:", remaining)
            raise RuntimeError(f"Checkout incomplete, remaining files: {remaining}")

        self._dbg("checkout complete, expected files present and no unexpected files remain.")

