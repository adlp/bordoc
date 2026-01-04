from pathlib import Path
from contextlib import contextmanager
import os

from dulwich.repo import Repo
from dulwich import porcelain
from dulwich.errors import NotGitRepository
from dulwich.index import IndexEntry

import shutil


@contextmanager
def chdir(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class TrueGit:
    def __init__(self, repo_path, default_branch: str = "main"):
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch
    
        repo_created = False
    
        # ------------------------------------------------------------
        # 1. Initialisation du repo si nécessaire
        # ------------------------------------------------------------
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            porcelain.init(str(self.repo_path))
            repo_created = True
    
        # Charger le repo Dulwich
        self.repo = Repo(str(self.repo_path))
    
        master_ref = b"refs/heads/master"
        main_ref   = f"refs/heads/{self.default_branch}".encode()
    
        # ------------------------------------------------------------
        # 2. Si master existe mais pas main → créer main à partir de master
        # ------------------------------------------------------------
        if master_ref in self.repo.refs and main_ref not in self.repo.refs:
            self.repo.refs[main_ref] = self.repo.refs[master_ref]
    
        # ------------------------------------------------------------
        # 3. HEAD → main (toujours)
        #    On ne crée PAS main si elle n'existe pas encore : branche unborn OK.
        # ------------------------------------------------------------
        head_file = self.repo_path / ".git" / "HEAD"
        head_file.write_text(
            f"ref: refs/heads/{self.default_branch}\n",
            encoding="utf-8"
        )
    
        # ------------------------------------------------------------
        # 4. Si le repo vient d’être créé → faire un commit initial
        # ------------------------------------------------------------
        if repo_created:
            # Créer un fichier vide pour pouvoir committer
            init_file = self.repo_path / ".gitignore"
            init_file.write_text("# initial\n")
    
            with chdir(self.repo_path):
                porcelain.add(".", paths=[".gitignore"])
                porcelain.commit(
                    ".",
                    message="First",
                    author="truegit <local>",
                    committer="truegit <local>",
                )
    
    

    # ------------------------------------------------------------
    # Utilitaires refs / branche courante
    # ------------------------------------------------------------

    def current_branch(self) -> str:
        """Retourne le nom de la branche courante (ou 'HEAD' si détaché)."""
        head_file = self.repo_path / ".git" / "HEAD"
        try:
            content = head_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return "HEAD"

        if content.startswith("ref:"):
            return content.split("/")[-1]
        return "HEAD"

    # ------------------------------------------------------------
    # Status / log / branches
    # ------------------------------------------------------------

    def status(self):
        """Retourne le status Dulwich (staged / unstaged)."""
        with chdir(self.repo_path):
            return porcelain.status(".")

    def branches(self):
        """Liste des branches locales (noms simples)."""
        return [
            ref.decode().split("/")[-1]
            for ref in self.repo.refs.keys()
            if ref.startswith(b"refs/heads/")
        ]

    def log(self, branch: str | None = None):
        """Retourne une liste de commits (sha, author, message, time) pour une branche."""
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
                    "sha": commit.id.decode(),
                    "author": commit.author.decode(),
                    "message": commit.message.decode().strip(),
                    "time": commit.commit_time,
                }
            )
        return commits

    # ------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------

    def create_branch(self, branch: str):
        """Crée une branche à partir de HEAD."""
        ref = f"refs/heads/{branch}".encode()
        head_sha = self.repo.refs.read_ref(b"HEAD")
        self.repo.refs[ref] = head_sha

    def delete_branch(self, branch: str):
        ref = f"refs/heads/{branch}".encode()
        if ref in self.repo.refs:
            del self.repo.refs[ref]


    def checkout(self, branch: str):
        """
        Checkout robuste et sûr :
        - met HEAD en premier et recharge Dulwich
        - calcule les chemins attendus
        - supprime uniquement les fichiers/dirs non attendus (NE TOUCHE PAS .git)
        - recrée les fichiers attendus
        - reconstruit l'index
        - vérifie l'absence de fichiers orphelins
        """
        ref = f"refs/heads/{branch}".encode()
        if ref not in self.repo.refs:
            raise ValueError(f"La branche {branch} n'existe pas")
    
        # 0) HEAD -> branch (premier) et rechargement du repo
        head_file = self.repo_path / ".git" / "HEAD"
        head_file.write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
        self.repo = Repo(str(self.repo_path))
    
        # 1) lire commit et tree
        commit_sha = self.repo.refs[ref]
        commit = self.repo[commit_sha]
        tree = self.repo[commit.tree]
    
        # 2) collecter chemins attendus (posix relative)
        def collect_tree_paths(tree_obj, base=""):
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
        print("DEBUG: expected paths:", sorted(expected))
    
        git_dir = (self.repo_path / ".git").resolve()
    
        # helper: is path inside .git ?
        def is_in_git(path: Path):
            try:
                return git_dir == path.resolve() or git_dir in path.resolve().parents
            except Exception:
                return False
    
        # 3) supprimer tout fichier/liaison non attendu (skip .git)
        for root, dirs, files in os.walk(self.repo_path, topdown=False):
            root_path = Path(root)
            # skip any path that is inside .git
            if is_in_git(root_path):
                continue
    
            # fichiers et liens
            for f in files:
                full_path = root_path / f
                # skip if inside .git just in case
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
    
            # dossiers : tenter rmdir, sinon rmtree si non attendu and not .git
            for d in dirs:
                dpath = root_path / d
                # skip .git or anything inside it
                if is_in_git(dpath):
                    continue
                rel_dir = os.path.relpath(dpath, self.repo_path).replace(os.sep, "/")
                has_expected_under = any(p == rel_dir or p.startswith(rel_dir + "/") for p in expected)
                if not has_expected_under:
                    try:
                        dpath.rmdir()
                        print("DEBUG: removed empty dir", rel_dir)
                    except OSError:
                        # not empty: remove recursively (but ensure not .git)
                        try:
                            shutil.rmtree(dpath)
                            print("DEBUG: rmtree removed dir", rel_dir)
                        except Exception as e:
                            print("WARN: failed to rmtree", rel_dir, ":", e)
    
        # 4) recréer les fichiers attendus depuis le tree
        def checkout_tree(tree_obj, base_path: Path):
            for name in tree_obj:
                mode, sha = tree_obj[name]
                obj = self.repo[sha]
                name_str = name.decode() if isinstance(name, bytes) else name
                path = base_path / name_str
                # never create inside .git
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
    
        # 5) reconstruire l'index depuis le tree
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
    
        add_tree_to_index(tree)
        index.write()
    
        # 6) vérification finale : aucun fichier non attendu ne doit subsister
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
    

    # ------------------------------------------------------------
    # Fichiers
    # ------------------------------------------------------------

    def read(self, filepath: str, branch: str | None = None) -> str:
        """Lit un fichier dans une branche donnée (ou branche courante)."""
        branch = branch or self.current_branch()
        ref = f"refs/heads/{branch}".encode()

        if ref not in self.repo.refs:
            raise ValueError(f"La branche {branch} n'existe pas")

        commit = self.repo[self.repo.refs[ref]]
        tree = self.repo[commit.tree]

        parts = filepath.strip("/").split("/")
        obj = tree
        for part in parts:
            key = part.encode()
            mode, sha = obj[key]
            obj = self.repo[sha]

        return obj.data.decode()

    def add(self, filepath: str):
        """Stage un fichier (équivalent git add)."""
        with chdir(self.repo_path):
            porcelain.add(".", paths=[filepath])

    def rm(self, filepath: str):
        """Supprime un fichier du FS et stage sa suppression."""
        full_path = (self.repo_path / filepath).resolve()
        if full_path.exists():
            full_path.unlink()
        with chdir(self.repo_path):
            porcelain.add(".", paths=[filepath])

    def commit(self, message: str, author: str = "truegit <local>") -> str:
        """Crée un commit avec l'index courant."""
        with chdir(self.repo_path):
            commit_id = porcelain.commit(
                ".",
                message=message,
                author=author,
                committer=author,
            )
        sha = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
        # Dulwich met déjà à jour HEAD + branche : ne pas toucher aux refs ici.
        return sha

    def write(
        self,
        filepath: str,
        content: str,
        branch: str | None = None,
        message: str = "update",
        author: str = "truegit <local>",
    ) -> str:
        """
        Écrit un fichier, l'ajoute et commit.
        Si branch est donnée, assure l'écriture sur cette branche.
        """
        filepath = filepath.strip("/")
        full_path = (self.repo_path / filepath).resolve()

        # Gestion de la branche cible
        if branch is not None:
            ref = f"refs/heads/{branch}".encode()
            if ref not in self.repo.refs:
                self.create_branch(branch)
            if self.current_branch() != branch:
                self.checkout(branch)

        # Écrire le fichier sur le FS
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

        sha = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
        return sha

