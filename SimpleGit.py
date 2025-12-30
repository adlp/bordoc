import os
from pathlib import Path
from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.objects import Blob
from dulwich.errors import NotGitRepository


class SimpleGit:
    # ------------------------------------------------------------
    # UTILITAIRE : CONTEXTE chdir
    # ------------------------------------------------------------
    class _ChDir:
        def __init__(self, new_path):
            self.new_path = new_path
            self.old_path = os.getcwd()

        def __enter__(self):
            os.chdir(self.new_path)

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self.old_path)

    # ------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------
    def __init__(self, path):
        self.repo_path = Path(path).resolve()

        if not self.repo_path.exists():
            self.repo_path.mkdir(parents=True)

        # Toujours ouvrir le repo depuis le chemin fourni
        try:
            self.repo = Repo(str(self.repo_path))
        except NotGitRepository:
            self.repo = Repo.init(str(self.repo_path))

        # Vérifier si une branche existe déjà
        heads = [ref for ref in self.repo.refs.keys() if ref.startswith(b"refs/heads/")]

        if not heads:
            # Création du commit initial
            with self._ChDir(self.repo_path):
                tmp = self.repo_path / ".init"
                tmp.write_text("init", encoding="utf-8")

                porcelain.add(str(self.repo_path), paths=[".init"])
                porcelain.commit(
                    str(self.repo_path),
                    message="Initial commit",
                    author="simplegit <local>",
                )

                sha = self.repo.head()
                self.repo.refs[b"refs/heads/main"] = sha
                self.repo.refs.set_symbolic_ref(b"HEAD", b"refs/heads/main")

                tmp.unlink()
                porcelain.add(str(self.repo_path), paths=[".init"])
                porcelain.commit(
                    str(self.repo_path),
                    message="Cleanup init",
                    author="simplegit <local>",
                )

        # Si main n'existe pas mais d'autres branches existent
        if b"refs/heads/main" not in self.repo.refs:
            sha = self.repo.head()
            self.repo.refs[b"refs/heads/main"] = sha
            self.repo.refs.set_symbolic_ref(b"HEAD", b"refs/heads/main")


    # ------------------------------------------------------------
    # WRITE FILE
    # ------------------------------------------------------------
    def write(self, filepath, content, branch="main", message="update"):
        filepath = filepath.strip("/")
        full_path = self.repo_path / filepath
    
        try:
            # 1) Lire l'ancien contenu depuis Git
            old = self.read(filepath, branch=branch)
            if old["success"] and old["content"] == content:
                return {
                    "success": True,
                    "created": False,
                    "commit": None,
                    "branch": branch,
                    "file": filepath,
                    "message": "No changes",
                    "error": None,
                }
    
            # 2) Écrire le fichier
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
    
            # 3) Préparer la branche
            ref = f"refs/heads/{branch}".encode()
            if ref not in self.repo.refs:
                sha = self.repo.head()
                self.repo.refs[ref] = sha
    
            self.repo.refs.set_symbolic_ref(b"HEAD", ref)
    
            # 4) Ajouter et committer
            with self._ChDir(self.repo_path):
                porcelain.add(str(self.repo_path), paths=[filepath])
                porcelain.commit(
                    str(self.repo_path),
                    message=message,
                    author="simplegit <local>",
                )
    
            after = self.repo.head()
    
            return {
                "success": True,
                "created": True,
                "commit": after.decode(),
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


    # ------------------------------------------------------------
    # READ FILE
    # ------------------------------------------------------------
    def read(self, filepath, branch="main", commit_id=None):
        filepath = filepath.strip("/")

        try:
            if commit_id:
                commit = self.repo[commit_id]
            else:
                ref = f"refs/heads/{branch}".encode()
                commit = self.repo[ref]

            tree = self.repo[commit.tree]

            parts = filepath.split("/")
            obj = tree

            for p in parts:
                p = p.encode()
                if p not in obj:
                    return {
                        "success": False,
                        "content": None,
                        "branch": branch,
                        "file": filepath,
                        "commit": None,
                        "error": f"File '{filepath}' not found",
                    }

                mode, sha = obj[p]
                obj = self.repo[sha]

            if not isinstance(obj, Blob):
                return {
                    "success": False,
                    "content": None,
                    "branch": branch,
                    "file": filepath,
                    "commit": None,
                    "error": f"'{filepath}' is not a file",
                }

            return {
                "success": True,
                "content": obj.data.decode("utf-8"),
                "branch": branch,
                "file": filepath,
                "commit": commit.id.decode(),
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


    # ------------------------------------------------------------
    # LIST FILES
    # ------------------------------------------------------------

    def ls(self, path="", branch="main"):
        path = path.strip("/")
    
        try:
            with self._ChDir(self.repo_path):
                ref = f"refs/heads/{branch}".encode()
                commit = self.repo[ref]
                tree = self.repo[commit.tree]
        
                print(tree)
                print(path)
                # Descendre dans l'arborescence uniquement si ce sont des dossiers
                if path:
                    for p in path.split("/"):
                        entry = tree.get(p.encode())
                        print(p)
                        print(entry)
                        if entry is None:
                            raise FileNotFoundError(f"{p} not found")
        
                        mode, sha = entry
                        obj = self.repo[sha]
        
                        # Si ce n'est pas un Tree → erreur
                        if obj.type_name != b"tree":
                            raise NotADirectoryError(f"{path} is not a directory")
        
                        tree = obj
        
                # Maintenant tree est garanti être un Tree
                print("puette")
                print(tree.items())
                print("puette")
                for name, mode, sha in tree.items():
                    print(name)
                print("pouette")
                files = [name.decode() for name, mode, sha in tree.items()]
                print("pouette")
                print(tree.items())
                return {
                    "success": True,
                    "branch": branch,
                    "path": path or ".",
                    "files": files,
                    "error": None,
                }
    
        except Exception as e:
            return {
                "success": False,
                "branch": branch,
                "path": path or ".",
                "files": [],
                "error": str(e),
            }


    # ------------------------------------------------------------
    # DELETE FILE
    # ------------------------------------------------------------
    def delete(self, filepath, branch="main", message="delete"):
        filepath = filepath.strip("/")
        full_path = self.repo_path / filepath

        try:
            if full_path.exists():
                full_path.unlink()

            with self._ChDir(self.repo_path):
                porcelain.add(str(self.repo_path), paths=[filepath])
                porcelain.commit(
                    str(self.repo_path),
                    message=message,
                    author="simplegit <local>",
                )

            after = self.repo.head()

            return {
                "success": True,
                "deleted": True,
                "commit": after.decode(),
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


    # ------------------------------------------------------------
    # RENAME FILE
    # ------------------------------------------------------------
    def rename(self, old_path, new_path, branch="main", message="rename"):
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

            new_full.parent.mkdir(parents=True, exist_ok=True)
            old_full.rename(new_full)

            with self._ChDir(self.repo_path):
                porcelain.add(str(self.repo_path), paths=[old_path, new_path])
                porcelain.commit(
                    str(self.repo_path),
                    message=message,
                    author="simplegit <local>",
                )

            after = self.repo.head()

            return {
                "success": True,
                "renamed": True,
                "branch": branch,
                "old": old_path,
                "new": new_path,
                "commit": after.decode(),
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


    # ------------------------------------------------------------
    # LIST BRANCHES
    # ------------------------------------------------------------
    def branches(self):
        try:
            branches = [
                name.decode().replace("refs/heads/", "")
                for name in self.repo.refs.keys()
                if name.startswith(b"refs/heads/")
            ]
            return {
                "success": True,
                "branches": branches,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "branches": [],
                "error": str(e),
            }


    # ------------------------------------------------------------
    # LOGS
    # ------------------------------------------------------------
    def logs(self, filepath=None, max_entries=100):
        try:
            args = {}
            if filepath:
                args["paths"] = [filepath.strip("/")]

            with self._ChDir(self.repo_path):
                entries = porcelain.log(str(self.repo_path), max_entries=max_entries, **args)

            logs_list = []
            for e in entries:
                logs_list.append({
                    "id": e.id.decode(),
                    "message": e.message.decode(),
                })

            return {
                "success": True,
                "logs": logs_list,
                "file": filepath,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "logs": [],
                "file": filepath,
                "error": str(e),
            }


    # ------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------
    def status(self):
        try:
            with self._ChDir(self.repo_path):
                st = porcelain.status(str(self.repo_path))

            return {
                "success": True,
                "staged": {
                    "added": st.staged["add"],
                    "modified": st.staged["modify"],
                    "deleted": st.staged["delete"],
                },
                "unstaged": st.unstaged,
                "untracked": st.untracked,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "staged": {},
                "unstaged": [],
                "untracked": [],
                "error": str(e),
            }

