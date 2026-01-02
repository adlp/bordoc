from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.objects import Commit


@contextmanager
def chdir(path: Path | str):
    old = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(old)


@dataclass
class SimpleGitResult:
    success: bool
    message: str
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SimpleGit:
    def __init__(self, repo_path: str | Path, default_branch: str = "main"):
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch
    
        # Créer le repo s'il n'existe pas
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            porcelain.init(str(self.repo_path))
    
        # Charger le repo
        self.repo = Repo(str(self.repo_path))
    
        # ------------------------------------------------------------
        # Supprimer master créé automatiquement par Dulwich
        # ------------------------------------------------------------
        with chdir(self.repo_path):
            refs = self.repo.refs
    
            master_ref = b"refs/heads/master"
    
            # Si master existe mais ne pointe sur aucun commit → on le supprime
            if master_ref in refs:
                try:
                    _ = self.repo[refs[master_ref]]
                except Exception:
                    del refs[master_ref]
    
            # IMPORTANT : HEAD doit pointer vers main SYMBOLIQUEMENT
            # mais la branche main NE DOIT PAS être créée ici.
            refs.set_symbolic_ref(b"HEAD", f"refs/heads/{self.default_branch}".encode())
    
    def __initmaster(self, repo_path: str | Path, default_branch: str = "main"):
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch
    
        # Créer le repo s'il n'existe pas
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            porcelain.init(str(self.repo_path))
    
        # Charger le repo
        self.repo = Repo(str(self.repo_path))

    
    def __initii(self, repo_path: str | Path, default_branch: str = "main"):
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch
    
        # Créer le repo s'il n'existe pas
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            porcelain.init(str(self.repo_path))
    
        # Charger le repo
        self.repo = Repo(str(self.repo_path))
    
        # ------------------------------------------------------------
        # CORRECTIF : supprimer master créé automatiquement par Dulwich
        # ------------------------------------------------------------
        with chdir(self.repo_path):
            refs = self.repo.refs
    
            master_ref = b"refs/heads/master"
    
            # Si master existe mais ne pointe sur aucun commit → on le supprime
            if master_ref in refs:
                try:
                    _ = self.repo[refs[master_ref]]
                except Exception:
                    del refs[master_ref]
    
            # IMPORTANT : HEAD doit pointer vers une branche SYMBOLIQUE,
            # mais cette branche n'existe pas encore.
            # On le met sur refs/heads/main AVANT que la branche existe.
            refs.set_symbolic_ref(b"HEAD", b"refs/heads/main")
    

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------

    def _get_head_branch(self) -> Optional[str]:
        try:
            with chdir(self.repo_path):
                ref = self.repo.refs.read_ref(b"HEAD")
                if ref and ref.startswith(b"refs/heads/"):
                    return ref.decode().split("refs/heads/")[1]
        except Exception:
            pass
        return None

    def _get_head_commit(self, branch: Optional[str] = None) -> Optional[Commit]:
        branch = branch or self._get_head_branch()
        if not branch:
            return None
        ref = f"refs/heads/{branch}".encode()
        if ref not in self.repo.refs:
            return None
        return self.repo[self.repo.refs[ref]]

    def _ensure_branch(self, branch: str) -> SimpleGitResult:
        branch = branch.strip()
        ref = f"refs/heads/{branch}".encode()

        with chdir(self.repo_path):
            refs = self.repo.refs

            if ref not in refs:
                head_commit = self._get_head_commit()
                if not head_commit:
                    return SimpleGitResult(False, "Cannot create branch: no commit exists yet", error="no_head")
                refs[ref] = head_commit.id

            refs.set_symbolic_ref(b"HEAD", ref)

        return SimpleGitResult(True, "Branch ready", data={"branch": branch})

    def _create_commit(self, message: str, author: str = "simplegit <local>") -> Optional[str]:
        repo_path = str(self.repo_path)

        with chdir(self.repo_path):
            status = porcelain.status(repo_path)

            if (
                not status.staged["add"]
                and not status.staged["modify"]
                and not status.staged["delete"]
                and not status.unstaged
                and not status.untracked
            ):
                return None

            porcelain.add(repo_path, paths=["."])

            commit_id = porcelain.commit(
                repo_path,
                message=message,
                author=author.encode(),
                committer=author.encode(),
                #encoding="utf-8",
            )

        return commit_id.decode()
    # ------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------
    def write(
        self,
        filepath: str,
        content: str,
        branch: Optional[str] = "main",
        message: str = "update",
        author: str = "simplegit <local>",
    ) -> SimpleGitResult:
    
        try:
            filepath = filepath.strip("/")
            full_path = (self.repo_path / filepath).resolve()
            target_branch = branch or self.default_branch
            ref = f"refs/heads/{target_branch}".encode()
    
            repo_path = str(self.repo_path)
    
            # ------------------------------------------------------------
            # 1. Vérifier si la branche existe
            # ------------------------------------------------------------
            branch_exists = ref in self.repo.refs
    
            # ------------------------------------------------------------
            # 2. CAS : premier commit de cette branche
            # ------------------------------------------------------------
            if not branch_exists:
                # Écrire le fichier
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
    
                with chdir(self.repo_path):
                    # git add <filepath>
                    porcelain.add(repo_path, paths=[filepath])
    
                    # git commit -m "Initial commit"
                    commit_id = porcelain.commit(
                        repo_path,
                        message="Initial commit",
                        author=author,
                        committer=author,
                    )
    
                    # SHA propre
                    sha = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
    
                    # Créer la branche proprement
                    self.repo.refs[ref] = sha.encode()
    
                    # HEAD → branche
                    self.repo.refs.set_symbolic_ref(b"HEAD", ref)
    
                return SimpleGitResult(
                    True,
                    "Initial commit created",
                    data={"file": filepath, "commit": sha, "branch": target_branch},
                )
    
            # ------------------------------------------------------------
            # 3. Branche existante → basculer dessus
            # ------------------------------------------------------------
            with chdir(self.repo_path):
                self.repo.refs.set_symbolic_ref(b"HEAD", ref)
    
            # ------------------------------------------------------------
            # 4. Écriture normale
            # ------------------------------------------------------------
            old_content = full_path.read_text(encoding="utf-8") if full_path.exists() else None
    
            if old_content == content:
                return SimpleGitResult(True, "No changes", data={"file": filepath})
    
            # Écrire le fichier
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
    
            with chdir(self.repo_path):
                # git add <filepath>
                porcelain.add(repo_path, paths=[filepath])
    
                # git commit -m "<message>"
                commit_id = porcelain.commit(
                    repo_path,
                    message=message,
                    author=author,
                    committer=author,
                )
    
                sha = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
    
                # Mettre à jour la branche
                self.repo.refs[ref] = sha.encode()
    
            return SimpleGitResult(
                True,
                "File written and committed",
                data={"file": filepath, "commit": sha},
            )
    
        except Exception as e:
            return SimpleGitResult(False, "Write failed", error=str(e))
    

    def delete(self, filepath: str, message: str = "delete", author: str = "simplegit <local>") -> SimpleGitResult:
        try:
            filepath = filepath.strip("/")
            full_path = (self.repo_path / filepath).resolve()

            existed = full_path.exists()
            if existed:
                full_path.unlink()

            commit_id = self._create_commit(message=message, author=author)

            return SimpleGitResult(True,
                                   "File deleted and committed" if existed and commit_id else "Nothing to delete",
                                   data={"file": filepath, "commit": commit_id})

        except Exception as e:
            return SimpleGitResult(False, "Delete failed", error=str(e))

    def read(self, filepath: str) -> SimpleGitResult:
        try:
            filepath = filepath.strip("/")
            full_path = (self.repo_path / filepath).resolve()

            if not full_path.exists():
                return SimpleGitResult(False, "File does not exist", error="not_found")

            return SimpleGitResult(True, "File read",
                                   data={"file": filepath, "content": full_path.read_text(encoding="utf-8")})

        except Exception as e:
            return SimpleGitResult(False, "Read failed", error=str(e))

    def list(self, path: str = "") -> SimpleGitResult:
        try:
            base = (self.repo_path / path.strip("/")).resolve()
            if not base.exists():
                return SimpleGitResult(False, "Path does not exist", error="not_found")

            files = []
            for root, dirs, filenames in os.walk(base):
                root_path = Path(root)
                for name in filenames:
                    rel = root_path.joinpath(name).relative_to(self.repo_path)
                    files.append(str(rel))

            return SimpleGitResult(True, "List OK", data={"files": sorted(files)})

        except Exception as e:
            return SimpleGitResult(False, "List failed", error=str(e))

    def ls(self, path: str = "") -> SimpleGitResult:
        return self.list(path)

    # ------------------------------------------------------------
    # Status / branches / history / diff / repair
    # ------------------------------------------------------------

    def status(self) -> SimpleGitResult:
        try:
            with chdir(self.repo_path):
                st = porcelain.status(str(self.repo_path))

            return SimpleGitResult(True, "Status OK", data={
                "staged": {
                    "add": [p.decode() for p in st.staged["add"]],
                    "modify": [p.decode() for p in st.staged["modify"]],
                    "delete": [p.decode() for p in st.staged["delete"]],
                },
                "unstaged": [p.decode() for p in st.unstaged],
                "untracked": [p.decode() for p in st.untracked],
            })

        except Exception as e:
            return SimpleGitResult(False, "Status failed", error=str(e))

    def branches(self) -> SimpleGitResult:
        try:
            with chdir(self.repo_path):
                refs = self.repo.refs
                head = refs.read_ref(b"HEAD")
                current = head.decode().split("refs/heads/")[1] if head and head.startswith(b"refs/heads/") else None

                branches = sorted(
                    ref.decode().split("refs/heads/")[1]
                    for ref in refs.keys()
                    if ref.startswith(b"refs/heads/")
                )

            return SimpleGitResult(True, "Branches OK", data={"current": current, "branches": branches})

        except Exception as e:
            return SimpleGitResult(False, "Branches failed", error=str(e))

    def history(self, filepath: Optional[str] = None, max_entries: int = 50) -> SimpleGitResult:
        try:
            with chdir(self.repo_path):
                walker = self.repo.get_walker(max_entries=max_entries)

                commits = []
                for entry in walker:
                    commit: Commit = entry.commit
                    sha = commit.id.decode()
                    msg = commit.message.decode(errors="replace").strip()
                    author = commit.author.decode(errors="replace")

                    if filepath:
                        try:
                            tree = self.repo[commit.tree]
                            tree.lookup_path(self.repo.__getitem__, filepath.encode())
                        except KeyError:
                            continue

                    commits.append({"sha": sha, "author": author, "message": msg})

            return SimpleGitResult(True, "History OK", data={"commits": commits})

        except Exception as e:
            return SimpleGitResult(False, "History failed", error=str(e))

    def diff(self, rev1: str = "HEAD~1", rev2: str = "HEAD", filepath: Optional[str] = None) -> SimpleGitResult:
        try:
            args = [filepath] if filepath else None

            with chdir(self.repo_path):
                diff_bytes = porcelain.diff_tree(
                    str(self.repo_path),
                    rev1.encode(),
                    rev2.encode(),
                    paths=args,
                )

            return SimpleGitResult(True, "Diff OK",
                                   data={"rev1": rev1, "rev2": rev2, "filepath": filepath,
                                         "diff": diff_bytes.decode("utf-8", errors="replace")})

        except Exception as e:
            return SimpleGitResult(False, "Diff failed", error=str(e))

    def repair_repo(self) -> SimpleGitResult:
        try:
            with chdir(self.repo_path):
                refs = self.repo.refs
                head = refs.read_ref(b"HEAD")

                if head and head.startswith(b"ref:"):
                    real_ref = head.split(b" ", 1)[1].strip()
                    refs.set_symbolic_ref(b"HEAD", real_ref)

            return SimpleGitResult(True, "Repo repaired")

        except Exception as e:
            return SimpleGitResult(False, "Repair failed", error=str(e))

    # ------------------------------------------------------------
    # Branch management + push/pull
    # ------------------------------------------------------------

    def create_branch(self, name: str) -> SimpleGitResult:
        try:
            name = name.strip()
            if not name:
                return SimpleGitResult(False, "Invalid branch name")

            ref = f"refs/heads/{name}".encode()

            with chdir(self.repo_path):
                refs = self.repo.refs

                if ref in refs:
                    return SimpleGitResult(False, "Branch already exists", data={"branch": name})

                head_commit = self._get_head_commit()
                if not head_commit:
                    return SimpleGitResult(False, "No commit exists yet", error="no_head")

                refs[ref] = head_commit.id

            return SimpleGitResult(True, "Branch created", data={"branch": name})

        except Exception as e:
            return SimpleGitResult(False, "Create branch failed", error=str(e))

    def checkout(self, branch: str) -> SimpleGitResult:
        try:
            branch = branch.strip()
            ref = f"refs/heads/{branch}".encode()

            with chdir(self.repo_path):
                if ref not in self.repo.refs:
                    return SimpleGitResult(False, "Branch does not exist", data={"branch": branch})

                self.repo.refs.set_symbolic_ref(b"HEAD", ref)

            return SimpleGitResult(True, "Checked out branch", data={"branch": branch})

        except Exception as e:
            return SimpleGitResult(False, "Checkout failed", error=str(e))

    def move(self, src: str, dst: str, message: str = "move file",
             author: str = "simplegit <local>") -> SimpleGitResult:

        try:
            src = src.strip("/")
            dst = dst.strip("/")

            src_path = (self.repo_path / src).resolve()
            dst_path = (self.repo_path / dst).resolve()

            if not src_path.exists():
                return SimpleGitResult(False, "Source file does not exist", error="not_found")

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dst_path)

            commit_id = self._create_commit(message=message, author=author)

            return SimpleGitResult(True,
                                   "File moved and committed" if commit_id else "File moved (no commit)",
                                   data={"src": src, "dst": dst, "commit": commit_id})

        except Exception as e:
            return SimpleGitResult(False, "Move failed", error=str(e))

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> SimpleGitResult:
        try:
            branch = branch or self._get_head_branch()
            if not branch:
                return SimpleGitResult(False, "No branch to push", error="no_branch")

            with chdir(self.repo_path):
                porcelain.push(
                    str(self.repo_path),
                    remote_location=remote,
                    refspecs=[f"refs/heads/{branch}".encode()],
                )

            return SimpleGitResult(True, "Push OK", data={"remote": remote, "branch": branch})

        except Exception as e:
            return SimpleGitResult(False, "Push failed", error=str(e))

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> SimpleGitResult:
        try:
            branch = branch or self._get_head_branch()
            if not branch:
                return SimpleGitResult(False, "No branch to pull into", error="no_branch")

            with chdir(self.repo_path):
                porcelain.pull(
                    str(self.repo_path),
                    remote_location=remote,
                    refspecs=[f"refs/heads/{branch}".encode()],
                )

            return SimpleGitResult(True, "Pull OK", data={"remote": remote, "branch": branch})

        except Exception as e:
            return SimpleGitResult(False, "Pull failed", error=str(e))

