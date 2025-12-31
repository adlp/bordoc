from pathlib import Path
import os
from typing import Optional, List, Dict, Any

from dulwich.repo import Repo
from dulwich.objects import Blob, Tree, Commit
from dulwich.errors import NotGitRepository
from dulwich.index import build_index_from_tree, commit_tree
from dulwich.client import get_transport_and_path
from dulwich.refs import ANNOTATED_TAG_SUFFIX


class SimpleGit:
    def __init__(self, path: str):
        self.repo_path = Path(path).resolve()
        if not self.repo_path.exists():
            self.repo_path.mkdir(parents=True)

        try:
            self.repo = Repo(str(self.repo_path))
        except NotGitRepository:
            self.repo = Repo.init(str(self.repo_path))

        # Si aucun commit/branche, créer un commit initial sur main
        if not self.repo.refs.keys():
            self._initial_commit()

        # S’assurer qu’une branche main existe
        if b"refs/heads/main" not in self.repo.refs:
            head = self.repo.head()
            self.repo.refs[b"refs/heads/main"] = head
            self.repo.refs.set_symbolic_ref(b"HEAD", b"refs/heads/main")

    # ------------------------------------------------------------------
    # Internes
    # ------------------------------------------------------------------
    def _initial_commit(self):
        """
        Crée un commit initial vide sur main.
        """
        tree = Tree()
        tree_id = self.repo.object_store.add_object(tree)

        commit = Commit()
        commit.tree = tree_id
        commit.author = commit.committer = b"simplegit <local>"
        commit.message = b"Initial commit"
        commit.encoding = b"UTF-8"
        from time import time
        now = int(time())
        commit.commit_time = now
        commit.author_time = now
        commit.commit_timezone = 0
        commit.author_timezone = 0

        commit_id = self.repo.object_store.add_object(commit)

        self.repo.refs[b"refs/heads/main"] = commit_id
        self.repo.refs.set_symbolic_ref(b"HEAD", b"refs/heads/main")

    def _get_head_commit(self, branch: str) -> Commit:
        ref = f"refs/heads/{branch}".encode()
        if ref not in self.repo.refs:
            # si la branche n’existe pas, la créer à partir de HEAD
            base = self.repo.head()
            self.repo.refs[ref] = base
        return self.repo[self.repo.refs[ref]]

    def _build_working_tree_index(self, commit: Commit):
        """
        Reconstruit l’index à partir du tree de HEAD.
        """
        tree_id = commit.tree
        build_index_from_tree(
            self.repo.path,
            self.repo.index_path(),
            self.repo.object_store,
            tree_id,
        )

    def _get_blob_content_from_commit(
        self, commit: Commit, filepath: str
    ) -> Optional[bytes]:
        """
        Récupère le contenu d’un fichier dans un commit, ou None s’il n’existe pas.
        """
        tree = self.repo[commit.tree]
        parts = filepath.strip("/").split("/")
        cur = tree
        try:
            for p in parts:
                mode, sha = cur[p.encode()]
                obj = self.repo[sha]
                if isinstance(obj, Tree):
                    cur = obj
                else:
                    # dernier élément
                    if p == parts[-1]:
                        if isinstance(obj, Blob):
                            return obj.data
                        else:
                            return None
                    else:
                        return None
            return None
        except KeyError:
            return None

    def _create_commit(
        self,
        message: str,
        branch: str,
        parents: Optional[List[bytes]] = None,
    ) -> bytes:
        """
        Crée un commit à partir de l’index courant.
        """
        # Générer un tree à partir de l’index
        tree_id = commit_tree(self.repo.object_store, self.repo.index)

        commit = Commit()
        commit.tree = tree_id
        if parents:
            commit.parents = parents
        else:
            try:
                head = self._get_head_commit(branch)
                commit.parents = [head.id]
            except KeyError:
                commit.parents = []

        commit.author = commit.committer = b"simplegit <local>"
        commit.message = message.encode("utf-8")
        commit.encoding = b"UTF-8"

        from time import time
        now = int(time())
        commit.commit_time = now
        commit.author_time = now
        commit.commit_timezone = 0
        commit.author_timezone = 0

        commit_id = self.repo.object_store.add_object(commit)

        ref = f"refs/heads/{branch}".encode()
        self.repo.refs[ref] = commit_id
        # HEAD reste symbolique vers cette branche (pas besoin de le changer ici)

        return commit_id

    # ------------------------------------------------------------------
    # WRITE (avec commit seulement si changement)
    # ------------------------------------------------------------------
    def write(
        self,
        filepath: str,
        content: str,
        branch: str = "main",
        message: str = "update",
    ) -> Dict[str, Any]:
        filepath = filepath.strip("/")
        full_path = self.repo_path / filepath

        try:
            head_commit = self._get_head_commit(branch)
            old_content = self._get_blob_content_from_commit(head_commit, filepath)

            new_bytes = content.encode("utf-8")

            # Si le contenu n’a pas changé → pas de commit
            if old_content == new_bytes:
                return {
                    "success": True,
                    "created": False,
                    "commit": None,
                    "branch": branch,
                    "file": filepath,
                    "message": "No changes",
                    "error": None,
                }

            # Écrire le fichier sur disque
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

            # Rebuilder l’index depuis HEAD
            self._build_working_tree_index(head_commit)

            # Ajouter/mettre à jour ce fichier dans l’index
            rel_path = filepath.encode("utf-8")
            st = os.stat(str(full_path))
            with open(full_path, "rb") as f:
                blob = Blob.from_string(f.read())
            blob_id = self.repo.object_store.add_object(blob)

            # mode 0o100644 pour fichiers classiques
            from dulwich.index import index_entry_from_stat
            entry = index_entry_from_stat(
                st, blob_id, 0o100644
            )
            self.repo.index[rel_path] = entry
            self.repo.index.write()

            # Commit
            commit_id = self._create_commit(message=message, branch=branch)

            return {
                "success": True,
                "created": True,
                "commit": commit_id.hex(),
                "branch": branch,
                "file": filepath,
                "message": message,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "created": False,
                "commit": None,
                "branch": branch,
                "file": filepath,
                "message": message,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------
    def read(
        self,
        filepath: str,
        branch: str = "main",
        commit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        filepath = filepath.strip("/")

        try:
            if commit_id:
                commit = self.repo[bytes.fromhex(commit_id)]
            else:
                commit = self._get_head_commit(branch)

            data = self._get_blob_content_from_commit(commit, filepath)

            if data is None:
                return {
                    "success": False,
                    "content": None,
                    "branch": branch,
                    "file": filepath,
                    "commit": None if not commit_id else commit_id,
                    "error": f"File '{filepath}' not found",
                }

            return {
                "success": True,
                "content": data.decode("utf-8"),
                "branch": branch,
                "file": filepath,
                "commit": commit.id.hex(),
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "content": None,
                "branch": branch,
                "file": filepath,
                "commit": None,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # LS
    # ------------------------------------------------------------------
    def ls(self, path: str = "", branch: str = "main") -> Dict[str, Any]:
        path = path.strip("/")
    
        try:
            commit = self._get_head_commit(branch)
            tree = self.repo[commit.tree]
    
            # Descente dans l'arborescence si path est fourni
            if path:
                parts = path.split("/")
                cur = tree
                for p in parts:
                    try:
                        mode, sha = cur[p.encode()]
                    except KeyError:
                        raise FileNotFoundError(f"{path} not found")
                    obj = self.repo[sha]
                    if not isinstance(obj, Tree):
                        raise NotADirectoryError(f"{path} is not a directory")
                    cur = obj
                tree = cur
    
            entries = []
    
            for name, mode, sha in tree.items():
                name_str = name.decode()
                obj = self.repo[sha]
    
                # Déterminer le type
                if isinstance(obj, Tree):
                    entry_type = "directory"
                elif isinstance(obj, Blob):
                    if mode == 0o120000:
                        entry_type = "symlink"
                    else:
                        entry_type = "file"
                else:
                    entry_type = "unknown"
    
                # Branches où l'entrée diffère
                changed_in = []
    
                for ref in self.repo.refs.keys():
                    if not ref.startswith(b"refs/heads/"):
                        continue
    
                    other_branch = ref.decode().replace("refs/heads/", "")
                    if other_branch == branch:
                        continue
    
                    other_commit = self._get_head_commit(other_branch)
                    other_tree = self.repo[other_commit.tree]
    
                    try:
                        cur = other_tree
                        if path:
                            for p in path.split("/"):
                                m2, s2 = cur[p.encode()]
                                cur = self.repo[s2]
    
                        # Maintenant cur est le tree correspondant
                        m2, s2 = cur[name]
                        if s2 != sha:
                            changed_in.append(other_branch)
    
                    except Exception:
                        # Le fichier n'existe pas dans cette branche → considéré comme différent
                        changed_in.append(other_branch)
    
                entries.append({
                    "name": name_str,
                    "type": entry_type,
                    "mode": mode,
                    "sha": sha.hex(),
                    "changed_in_branches": changed_in,
                })
    
            return {
                "success": True,
                "branch": branch,
                "path": path or ".",
                "entries": entries,
                "error": None,
            }
    
        except Exception as e:
            return {
                "success": False,
                "branch": branch,
                "path": path or ".",
                "entries": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete(
        self,
        filepath: str,
        branch: str = "main",
        message: str = "delete",
    ) -> Dict[str, Any]:
        filepath = filepath.strip("/")
        full_path = self.repo_path / filepath

        try:
            head_commit = self._get_head_commit(branch)
            self._build_working_tree_index(head_commit)

            rel_path = filepath.encode("utf-8")

            # Supprimer du système de fichiers
            if full_path.exists():
                full_path.unlink()

            # Supprimer de l’index si présent
            if rel_path in self.repo.index:
                del self.repo.index[rel_path]
                self.repo.index.write()
            else:
                return {
                    "success": False,
                    "deleted": False,
                    "commit": None,
                    "branch": branch,
                    "file": filepath,
                    "message": message,
                    "error": "File not tracked",
                }

            commit_id = self._create_commit(message=message, branch=branch)

            return {
                "success": True,
                "deleted": True,
                "commit": commit_id.hex(),
                "branch": branch,
                "file": filepath,
                "message": message,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "deleted": False,
                "commit": None,
                "branch": branch,
                "file": filepath,
                "message": message,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # RENAME
    # ------------------------------------------------------------------
    def rename(
        self,
        old_path: str,
        new_path: str,
        branch: str = "main",
        message: str = "rename",
    ) -> Dict[str, Any]:
        old_path = old_path.strip("/")
        new_path = new_path.strip("/")

        old_full = self.repo_path / old_path
        new_full = self.repo_path / new_path

        try:
            if not old_full.exists():
                return {
                    "success": False,
                    "renamed": False,
                    "branch": branch,
                    "old": old_path,
                    "new": new_path,
                    "commit": None,
                    "message": message,
                    "error": "Source file not found",
                }

            head_commit = self._get_head_commit(branch)
            self._build_working_tree_index(head_commit)

            # Renommer dans le FS
            new_full.parent.mkdir(parents=True, exist_ok=True)
            old_full.rename(new_full)

            # Mettre à jour l’index
            old_rel = old_path.encode("utf-8")
            new_rel = new_path.encode("utf-8")

            if old_rel in self.repo.index:
                entry = self.repo.index[old_rel]
                del self.repo.index[old_rel]

                # Adapter le path
                self.repo.index[new_rel] = entry
                self.repo.index.write()
            else:
                return {
                    "success": False,
                    "renamed": False,
                    "branch": branch,
                    "old": old_path,
                    "new": new_path,
                    "commit": None,
                    "message": message,
                    "error": "Source not tracked",
                }

            commit_id = self._create_commit(message=message, branch=branch)

            return {
                "success": True,
                "renamed": True,
                "branch": branch,
                "old": old_path,
                "new": new_path,
                "commit": commit_id.hex(),
                "message": message,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "renamed": False,
                "branch": branch,
                "old": old_path,
                "new": new_path,
                "commit": None,
                "message": message,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # BRANCHES
    # ------------------------------------------------------------------
    def branches(self) -> Dict[str, Any]:
        try:
            branches = [
                ref.decode().replace("refs/heads/", "")
                for ref in self.repo.refs.keys()
                if ref.startswith(b"refs/heads/")
            ]
            return {"success": True, "branches": branches, "error": None}
        except Exception as e:
            return {"success": False, "branches": [], "error": str(e)}

    def create_branch(self, name: str, from_branch: str = "main") -> Dict[str, Any]:
        try:
            src = f"refs/heads/{from_branch}".encode()
            dst = f"refs/heads/{name}".encode()

            if src not in self.repo.refs:
                return {
                    "success": False,
                    "branch": name,
                    "from": from_branch,
                    "error": "Source branch does not exist",
                }

            self.repo.refs[dst] = self.repo.refs[src]
            return {
                "success": True,
                "branch": name,
                "from": from_branch,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "branch": name,
                "from": from_branch,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # LOGS (simple)
    # ------------------------------------------------------------------
    def logs(self, branch: str = "main", max_entries: int = 100) -> Dict[str, Any]:
        try:
            ref = f"refs/heads/{branch}".encode()
            if ref not in self.repo.refs:
                return {"success": True, "logs": [], "branch": branch, "error": None}

            commit_id = self.repo.refs[ref]
            logs_list = []
            count = 0
            while commit_id and count < max_entries:
                commit = self.repo[commit_id]
                logs_list.append(
                    {
                        "id": commit.id.hex(),
                        "message": commit.message.decode("utf-8", errors="ignore"),
                    }
                )
                if commit.parents:
                    commit_id = commit.parents[0]
                else:
                    break
                count += 1

            return {"success": True, "logs": logs_list, "branch": branch, "error": None}
        except Exception as e:
            return {"success": False, "logs": [], "branch": branch, "error": str(e)}

    # ------------------------------------------------------------------
    # STATUS (très simplifié)
    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        # Ici on pourrait comparer FS vs index vs HEAD.
        # Pour l’instant, on expose juste les chemins de l’index.
        try:
            index_paths = [p.decode() for p in self.repo.index]
            return {
                "success": True,
                "tracked": index_paths,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "tracked": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # PUSH / PULL via Dulwich (SSH ou HTTPS)
    # ------------------------------------------------------------------
    def push(self, remote_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Push la branche locale vers un dépôt distant (SSH ou HTTPS),
        sans utiliser le binaire git.
        """
        try:
            client, path = get_transport_and_path(remote_url)

            ref_local = f"refs/heads/{branch}".encode()
            if ref_local not in self.repo.refs:
                return {
                    "success": False,
                    "branch": branch,
                    "remote": remote_url,
                    "error": "Local branch does not exist",
                }

            refs = self.repo.get_refs()
            def determine_wants(remote_refs):
                # On veut pousser ref_local -> même nom côté distant
                return [refs[ref_local]]

            client.send_pack(path, determine_wants, self.repo.generate_pack_data)

            return {
                "success": True,
                "branch": branch,
                "remote": remote_url,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "branch": branch,
                "remote": remote_url,
                "error": str(e),
            }

    def pull(self, remote_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Pull depuis un dépôt distant (SSH ou HTTPS).
        Ici on fait un fast-forward simple sur la branche.
        À utiliser dans ta commande quotidienne (toutes les 24h).
        """
        try:
            client, path = get_transport_and_path(remote_url)
            remote_refs = client.fetch(path, self.repo)

            local_ref = f"refs/heads/{branch}".encode()
            remote_ref = f"refs/heads/{branch}".encode()

            if remote_ref not in remote_refs:
                return {
                    "success": False,
                    "branch": branch,
                    "remote": remote_url,
                    "error": "Remote branch does not exist",
                }

            self.repo.refs[local_ref] = remote_refs[remote_ref]

            return {
                "success": True,
                "branch": branch,
                "remote": remote_url,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "branch": branch,
                "remote": remote_url,
                "error": str(e),
            }

