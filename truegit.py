import os
import hashlib
import zlib
import time
import shutil
import re
import struct
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import stat
from collections import deque
import difflib


class TrueGit:
    """Implémentation pure Python d'un client Git compatible avec les dépôts Git standard."""
    
    def __init__(self, repo_path: str, branch: str = "main", 
                 initial_commit: bool = False, 
                 initial_message: str = "Initial commit",
                 initial_author: str = "TrueGit <truegit@example.com>"):
        """
        Initialise un dépôt Git.
        
        Args:
            repo_path: Chemin du dépôt sur le disque
            branch: Nom de la branche (par défaut: main)
            initial_commit: Si True, crée un commit initial vide (par défaut: False)
            initial_message: Message du commit initial (par défaut: "Initial commit")
            initial_author: Auteur du commit initial (par défaut: "TrueGit <truegit@example.com>")
        """
        self.repo_path = Path(repo_path).absolute()
        self.git_dir = self.repo_path / ".git"
        self._current_branch = branch
        self.index = {}  # Simule l'index Git
        
        if not self.git_dir.exists():
            self._init_repository()
            
            # Créer un commit initial si demandé
            if initial_commit:
                self._create_initial_commit(initial_message, initial_author)
        else:
            # Le dépôt existe déjà, charger la branche courante
            self._load_current_branch()
    
    def _load_current_branch(self):
        """Charge la branche courante depuis HEAD."""
        head_file = self.git_dir / "HEAD"
        if head_file.exists():
            content = head_file.read_text().strip()
            if content.startswith("ref: refs/heads/"):
                self._current_branch = content.replace("ref: refs/heads/", "")
        
    def _init_repository(self):
        """Initialise la structure du dépôt Git."""
        dirs = [
            self.git_dir,
            self.git_dir / "objects",
            self.git_dir / "refs" / "heads",
            self.git_dir / "refs" / "tags",
            self.git_dir / "refs" / "remotes",
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        
        head_file = self.git_dir / "HEAD"
        head_file.write_text(f"ref: refs/heads/{self._current_branch}\n")
        
        config_file = self.git_dir / "config"
        config_file.write_text("[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n")
    
    def _create_initial_commit(self, message: str, author: str):
        """Crée un commit initial vide."""
        # Créer un tree vide
        tree_content = b""
        tree_sha = self._hash_object(tree_content, "tree")
        
        # Créer le commit initial (sans parent)
        date = int(time.time())
        commit_content = f"tree {tree_sha}\n"
        commit_content += f"author {author} {date} +0000\n"
        commit_content += f"committer {author} {date} +0000\n"
        commit_content += f"\n{message}\n"
        
        commit_sha = self._hash_object(commit_content.encode(), "commit")
        
        # Mettre à jour la référence de branche
        branch_file = self.git_dir / "refs" / "heads" / self._current_branch
        branch_file.parent.mkdir(parents=True, exist_ok=True)
        branch_file.write_text(f"{commit_sha}\n")
        
        # L'index reste vide (pas de fichiers)
        self.index.clear()
        self._write_index()
        
    def _hash_object(self, data: bytes, obj_type: str) -> str:
        """Hash un objet Git et le stocke."""
        header = f"{obj_type} {len(data)}\0".encode()
        store = header + data
        sha1 = hashlib.sha1(store).hexdigest()
        
        obj_dir = self.git_dir / "objects" / sha1[:2]
        obj_dir.mkdir(exist_ok=True)
        obj_file = obj_dir / sha1[2:]
        
        if not obj_file.exists():
            compressed = zlib.compress(store)
            obj_file.write_bytes(compressed)
        
        return sha1
    
    def _read_object(self, sha1: str) -> Tuple[str, bytes]:
        """Lit un objet Git depuis le dépôt."""
        obj_file = self.git_dir / "objects" / sha1[:2] / sha1[2:]
        
        if not obj_file.exists():
            raise ValueError(f"Objet {sha1} introuvable")
        
        compressed = obj_file.read_bytes()
        data = zlib.decompress(compressed)
        
        null_idx = data.index(b'\0')
        header = data[:null_idx].decode()
        content = data[null_idx + 1:]
        obj_type = header.split()[0]
        
        return obj_type, content
    
    def _parse_tree(self, tree_content: bytes) -> List[Tuple[str, str, str]]:
        """Parse le contenu d'un tree Git."""
        entries = []
        i = 0
        while i < len(tree_content):
            space_idx = tree_content.index(b' ', i)
            mode = tree_content[i:space_idx].decode()
            
            null_idx = tree_content.index(b'\0', space_idx)
            name = tree_content[space_idx + 1:null_idx].decode()
            
            sha1 = tree_content[null_idx + 1:null_idx + 21].hex()
            entries.append((mode, name, sha1))
            
            i = null_idx + 21
        
        return entries
    
    def _create_tree_from_index(self, path: Path = None) -> str:
        """Crée un objet tree à partir des fichiers du répertoire."""
        if path is None:
            path = self.repo_path
        
        entries = []
        
        for item in sorted(path.iterdir()):
            if item.name == ".git":
                continue
            
            if item.is_file():
                content = item.read_bytes()
                sha1 = self._hash_object(content, "blob")
                mode = "100644"
                if os.access(item, os.X_OK):
                    mode = "100755"
                entries.append((mode, item.name, sha1))
            elif item.is_dir():
                sha1 = self._create_tree_from_index(item)
                mode = "40000"
                entries.append((mode, item.name, sha1))
        
        # Si aucun fichier, créer un tree vide
        if not entries:
            return self._hash_object(b"", "tree")
        
        tree_content = b""
        for mode, name, sha1 in entries:
            tree_content += f"{mode} {name}\0".encode()
            tree_content += bytes.fromhex(sha1)
        
        return self._hash_object(tree_content, "tree")
    
    def _get_head_commit(self) -> Optional[str]:
        """Récupère le SHA-1 du commit HEAD."""
        branch_file = self.git_dir / "refs" / "heads" / self._current_branch
        if not branch_file.exists():
            return None
        return branch_file.read_text().strip()
    
    def current_branch(self) -> str:
        """Retourne la branche courante."""
        return self._current_branch
    
    def _parse_commit(self, commit_sha: str) -> Dict:
        """Parse un commit et retourne ses informations."""
        obj_type, content = self._read_object(commit_sha)
        if obj_type != "commit":
            raise ValueError(f"L'objet {commit_sha} n'est pas un commit")
        
        lines = content.decode().split('\n')
        commit_info = {"sha": commit_sha}
        
        for i, line in enumerate(lines):
            if line.startswith("tree "):
                commit_info["tree"] = line.split()[1]
            elif line.startswith("parent "):
                if "parents" not in commit_info:
                    commit_info["parents"] = []
                commit_info["parents"].append(line.split()[1])
            elif line.startswith("author "):
                commit_info["author"] = line[7:]
            elif line.startswith("committer "):
                commit_info["committer"] = line[10:]
            elif line == "":
                commit_info["message"] = '\n'.join(lines[i+1:]).strip()
                break
        
        return commit_info
    
    def _write_index(self):
        """Écrit un fichier index Git (format binaire simplifié version 2)."""
        index_file = self.git_dir / "index"
        
        # Si l'index est vide, supprimer le fichier
        if not self.index:
            if index_file.exists():
                index_file.unlink()
            return
        
        # Format Git index version 2
        entries = []
        for path, data in sorted(self.index.items()):
            # Stat du fichier
            file_path = self.repo_path / path
            if file_path.exists():
                stat_info = file_path.stat()
                ctime_s = int(stat_info.st_ctime)
                ctime_ns = int((stat_info.st_ctime - ctime_s) * 1000000000)
                mtime_s = int(stat_info.st_mtime)
                mtime_ns = int((stat_info.st_mtime - mtime_s) * 1000000000)
                dev = stat_info.st_dev & 0xFFFFFFFF  # Limiter à 32 bits
                ino = stat_info.st_ino & 0xFFFFFFFF  # Limiter à 32 bits
                mode = int(data['mode'], 8) if isinstance(data, dict) else 0o100644
                uid = stat_info.st_uid
                gid = stat_info.st_gid
                size = stat_info.st_size
            else:
                # Valeurs par défaut si le fichier n'existe pas
                ctime_s = ctime_ns = mtime_s = mtime_ns = 0
                dev = ino = uid = gid = size = 0
                mode = int(data.get('mode', '100644'), 8) if isinstance(data, dict) else 0o100644
            
            sha_bytes = bytes.fromhex(data['sha'] if isinstance(data, dict) else data)
            path_bytes = path.encode('utf-8')
            
            # Flags: assume-valid (1 bit) + extended (1 bit) + stage (2 bits) + name length (12 bits)
            flags = min(len(path_bytes), 0xFFF)
            
            # Construire l'entrée: 10 uint32 (40 bytes) + SHA-1 (20 bytes) + flags (2 bytes)
            entry = struct.pack('>10I',
                ctime_s, ctime_ns,
                mtime_s, mtime_ns,
                dev, ino, mode, uid, gid, size
            )
            entry += sha_bytes  # Ajouter les 20 bytes du SHA
            entry += struct.pack('>H', flags)  # Ajouter les flags (2 bytes)
            
            # Total jusqu'ici: 62 bytes
            
            # Ajouter le nom du fichier (sans NUL de terminaison)
            entry += path_bytes
            
            # Padding: aligner sur 8 octets
            # La longueur totale doit être un multiple de 8
            # On a: 62 (header) + len(path) bytes
            # On doit ajouter assez de NUL bytes pour atteindre le prochain multiple de 8
            # Il doit y avoir au moins 1 NUL byte après le nom
            total_len = 62 + len(path_bytes)
            # Calculer combien de NUL bytes ajouter (minimum 1, maximum 8)
            # pour que (62 + len(path) + padding) % 8 == 0
            padlen = 1
            while (total_len + padlen) % 8 != 0:
                padlen += 1
            
            entry += b'\x00' * padlen
            
            entries.append(entry)
        
        # Header: signature + version + nombre d'entrées
        header = b'DIRC'  # Signature
        header += struct.pack('>I', 2)  # Version 2
        header += struct.pack('>I', len(entries))  # Nombre d'entrées
        
        # Construire l'index complet
        index_content = header + b''.join(entries)
        
        # Calculer le SHA-1 du contenu
        index_sha = hashlib.sha1(index_content).digest()
        
        # Écrire le fichier
        index_file.write_bytes(index_content + index_sha)
    
    def _rebuild_index_from_tree(self, tree_sha: str, prefix: str = ""):
        """Reconstruit l'index à partir d'un tree après un commit."""
        self.index.clear()
        
        obj_type, content = self._read_object(tree_sha)
        if obj_type != "tree":
            return
        
        entries = self._parse_tree(content)
        
        for mode, name, sha1 in entries:
            path = f"{prefix}/{name}" if prefix else name
            
            if mode == "40000":  # Répertoire
                self._rebuild_index_from_tree(sha1, path)
            else:  # Fichier
                self.index[path] = {
                    'sha': sha1,
                    'mode': mode
                }
        
        # Écrire l'index mis à jour
        self._write_index()
    
    def add(self, *paths: str):
        """Ajoute des fichiers à l'index (staging area)."""
        for path_str in paths:
            path = Path(path_str)
            if not path.is_absolute():
                path = self.repo_path / path
            
            if not path.exists():
                raise FileNotFoundError(f"Le fichier {path} n'existe pas")
            
            if path.is_file():
                rel_path = path.relative_to(self.repo_path)
                content = path.read_bytes()
                # Créer le blob immédiatement pour que Git puisse le voir
                sha1 = self._hash_object(content, "blob")
                self.index[str(rel_path)] = {
                    'sha': sha1,
                    'mode': '100755' if os.access(path, os.X_OK) else '100644'
                }
            elif path.is_dir():
                for item in path.rglob('*'):
                    if item.is_file() and '.git' not in item.parts:
                        rel_path = item.relative_to(self.repo_path)
                        content = item.read_bytes()
                        sha1 = self._hash_object(content, "blob")
                        self.index[str(rel_path)] = {
                            'sha': sha1,
                            'mode': '100755' if os.access(item, os.X_OK) else '100644'
                        }
        
        # Écrire l'index pour que Git puisse le voir (format simplifié)
        self._write_index()
    
    def commit(self, message: str, author: Optional[str] = None, 
               committer: Optional[str] = None, date: Optional[int] = None) -> str:
        """Crée un commit."""
        if author is None:
            author = "TrueGit User <truegit@example.com>"
        if committer is None:
            committer = author
        if date is None:
            date = int(time.time())
        
        tree_sha = self._create_tree_from_index()
        parent_sha = self._get_head_commit()
        
        commit_content = f"tree {tree_sha}\n"
        if parent_sha:
            commit_content += f"parent {parent_sha}\n"
        commit_content += f"author {author} {date} +0000\n"
        commit_content += f"committer {committer} {date} +0000\n"
        commit_content += f"\n{message}\n"
        
        commit_sha = self._hash_object(commit_content.encode(), "commit")
        
        branch_file = self.git_dir / "refs" / "heads" / self._current_branch
        branch_file.parent.mkdir(parents=True, exist_ok=True)
        branch_file.write_text(f"{commit_sha}\n")
        
        # Après le commit, reconstruire l'index à partir du tree commité
        # pour que Git voit l'état correct
        self._rebuild_index_from_tree(tree_sha)
        
        return commit_sha
    
    def log(self, max_count: Optional[int] = None) -> List[Dict]:
        """Affiche l'historique des commits."""
        commits = []
        current_sha = self._get_head_commit()
        count = 0
        
        while current_sha and (max_count is None or count < max_count):
            try:
                commit_info = self._parse_commit(current_sha)
                commits.append(commit_info)
                current_sha = commit_info.get("parents", [None])[0]
                count += 1
            except:
                break
        
        return commits
    
    def create_branch(self, name: str):
        """Crée une nouvelle branche."""
        head_commit = self._get_head_commit()
        if not head_commit:
            raise ValueError("Impossible de créer une branche sans commit")
        branch_file = self.git_dir / "refs" / "heads" / name
        branch_file.parent.mkdir(parents=True, exist_ok=True)
        branch_file.write_text(f"{head_commit}\n")
    
    def delete_branch(self, name: str):
        """Supprime une branche."""
        branch_file = self.git_dir / "refs" / "heads" / name
        if branch_file.exists():
            branch_file.unlink()
    
    def list_branches(self) -> List[str]:
        """Liste toutes les branches."""
        branches_dir = self.git_dir / "refs" / "heads"
        branches = []
        for branch_file in branches_dir.rglob('*'):
            if branch_file.is_file():
                branch_name = str(branch_file.relative_to(branches_dir))
                prefix = "* " if branch_name == self._current_branch else "  "
                branches.append(f"{prefix}{branch_name}")
        return sorted(branches)
    
    def switch(self, branch_name: str):
        """Change de branche."""
        branch_file = self.git_dir / "refs" / "heads" / branch_name
        if not branch_file.exists():
            raise ValueError(f"La branche {branch_name} n'existe pas")
        
        self._current_branch = branch_name
        head_file = self.git_dir / "HEAD"
        head_file.write_text(f"ref: refs/heads/{branch_name}\n")
        
        self._checkout_tree(branch_file.read_text().strip())
    
    def _checkout_tree(self, commit_sha: str):
        """Restaure l'arborescence à partir d'un commit."""
        commit_info = self._parse_commit(commit_sha)
        tree_sha = commit_info["tree"]
        
        for item in self.repo_path.iterdir():
            if item.name != ".git":
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        
        self._extract_tree(tree_sha, self.repo_path)
    
    def _extract_tree(self, tree_sha: str, target_path: Path):
        """Extrait récursivement un tree dans un répertoire."""
        obj_type, content = self._read_object(tree_sha)
        entries = self._parse_tree(content)
        
        for mode, name, sha1 in entries:
            item_path = target_path / name
            
            if mode == "40000":
                item_path.mkdir(exist_ok=True)
                self._extract_tree(sha1, item_path)
            else:
                obj_type, blob_content = self._read_object(sha1)
                item_path.write_bytes(blob_content)
                if mode == "100755":
                    item_path.chmod(item_path.stat().st_mode | stat.S_IXUSR)
    
    def tag(self, name: str, commit_sha: Optional[str] = None):
        """Crée un tag."""
        if commit_sha is None:
            commit_sha = self._get_head_commit()
            if not commit_sha:
                raise ValueError("Aucun commit à tagger")
        
        tag_file = self.git_dir / "refs" / "tags" / name
        tag_file.parent.mkdir(parents=True, exist_ok=True)
        tag_file.write_text(f"{commit_sha}\n")
    
    def diff(self, commit1: Optional[str] = None, commit2: Optional[str] = None) -> str:
        """Affiche les différences entre deux commits ou entre working tree et HEAD."""
        if commit1 is None:
            return self._diff_working_tree()
        
        tree1 = self._get_tree_files(commit1)
        tree2 = self._get_tree_files(commit2 if commit2 else self._get_head_commit())
        
        return self._compute_diff(tree1, tree2)
    
    def _diff_working_tree(self) -> str:
        """Compare le working tree avec HEAD."""
        head_commit = self._get_head_commit()
        if not head_commit:
            return "Aucun commit HEAD"
        
        head_files = self._get_tree_files(head_commit)
        work_files = {}
        
        for item in self.repo_path.rglob('*'):
            if item.is_file() and '.git' not in item.parts:
                rel_path = str(item.relative_to(self.repo_path))
                work_files[rel_path] = item.read_text(errors='ignore')
        
        return self._compute_diff(head_files, work_files)
    
    def _get_tree_files(self, commit_sha: str, prefix: str = "") -> Dict[str, str]:
        """Récupère tous les fichiers d'un commit."""
        commit_info = self._parse_commit(commit_sha)
        tree_sha = commit_info["tree"]
        return self._walk_tree(tree_sha, prefix)
    
    def _walk_tree(self, tree_sha: str, prefix: str = "") -> Dict[str, str]:
        """Parcourt récursivement un tree."""
        files = {}
        obj_type, content = self._read_object(tree_sha)
        entries = self._parse_tree(content)
        
        for mode, name, sha1 in entries:
            path = f"{prefix}/{name}" if prefix else name
            
            if mode == "40000":
                files.update(self._walk_tree(sha1, path))
            else:
                obj_type, blob_content = self._read_object(sha1)
                files[path] = blob_content.decode(errors='ignore')
        
        return files
    
    def _compute_diff(self, files1: Dict[str, str], files2: Dict[str, str]) -> str:
        """Calcule le diff entre deux ensembles de fichiers."""
        all_files = set(files1.keys()) | set(files2.keys())
        diff_output = []
        
        for file in sorted(all_files):
            content1 = files1.get(file, "").splitlines(keepends=True)
            content2 = files2.get(file, "").splitlines(keepends=True)
            
            if content1 != content2:
                diff = difflib.unified_diff(content1, content2, 
                                           fromfile=f"a/{file}", 
                                           tofile=f"b/{file}")
                diff_output.append(''.join(diff))
        
        return '\n'.join(diff_output)
    
    def show(self, commit_sha: Optional[str] = None) -> str:
        """Affiche les informations d'un commit."""
        if commit_sha is None:
            commit_sha = self._get_head_commit()
        
        commit_info = self._parse_commit(commit_sha)
        output = f"commit {commit_sha}\n"
        output += f"Author: {commit_info['author']}\n"
        output += f"\n    {commit_info['message']}\n\n"
        
        if "parents" in commit_info:
            parent_files = self._get_tree_files(commit_info["parents"][0])
            current_files = self._get_tree_files(commit_sha)
            output += self._compute_diff(parent_files, current_files)
        
        return output
    
    def reset(self, commit_sha: str, hard: bool = False):
        """Reset vers un commit."""
        branch_file = self.git_dir / "refs" / "heads" / self._current_branch
        branch_file.write_text(f"{commit_sha}\n")
        
        if hard:
            self._checkout_tree(commit_sha)
    
    def mv(self, source: str, dest: str):
        """Déplace ou renomme un fichier."""
        src_path = self.repo_path / source
        dst_path = self.repo_path / dest
        
        if not src_path.exists():
            raise FileNotFoundError(f"{source} n'existe pas")
        
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
    
    def restore(self, path: str, source: Optional[str] = None):
        """Restaure un fichier depuis un commit."""
        if source is None:
            source = self._get_head_commit()
        
        commit_files = self._get_tree_files(source)
        if path not in commit_files:
            raise ValueError(f"{path} introuvable dans {source}")
        
        file_path = self.repo_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(commit_files[path])
    
    def grep(self, pattern: str, commit_sha: Optional[str] = None) -> List[str]:
        """Recherche un motif dans les fichiers."""
        if commit_sha:
            files = self._get_tree_files(commit_sha)
        else:
            files = {}
            for item in self.repo_path.rglob('*'):
                if item.is_file() and '.git' not in item.parts:
                    rel_path = str(item.relative_to(self.repo_path))
                    files[rel_path] = item.read_text(errors='ignore')
        
        results = []
        for filepath, content in files.items():
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(pattern, line):
                    results.append(f"{filepath}:{i}:{line}")
        
        return results
    
    def merge(self, branch_name: str) -> str:
        """Merge simple d'une branche (sans gestion des conflits)."""
        branch_file = self.git_dir / "refs" / "heads" / branch_name
        if not branch_file.exists():
            raise ValueError(f"La branche {branch_name} n'existe pas")
        
        other_commit = branch_file.read_text().strip()
        current_commit = self._get_head_commit()
        
        if not current_commit:
            raise ValueError("Aucun commit sur la branche courante")
        
        tree_sha = self._create_tree_from_index()
        
        commit_content = f"tree {tree_sha}\n"
        commit_content += f"parent {current_commit}\n"
        commit_content += f"parent {other_commit}\n"
        commit_content += f"author TrueGit <truegit@example.com> {int(time.time())} +0000\n"
        commit_content += f"committer TrueGit <truegit@example.com> {int(time.time())} +0000\n"
        commit_content += f"\nMerge branch '{branch_name}'\n"
        
        merge_sha = self._hash_object(commit_content.encode(), "commit")
        
        branch_file = self.git_dir / "refs" / "heads" / self._current_branch
        branch_file.write_text(f"{merge_sha}\n")
        
        return merge_sha
    
    def rebase(self, target_branch: str):
        """Rebase simplifié (rejoue les commits)."""
        target_file = self.git_dir / "refs" / "heads" / target_branch
        if not target_file.exists():
            raise ValueError(f"La branche {target_branch} n'existe pas")
        
        target_commit = target_file.read_text().strip()
        current_commits = self.log()
        
        # Sauvegarder la branche courante
        original_branch = self._current_branch
        
        self.reset(target_commit, hard=True)
        
        for commit in reversed(current_commits[:-1]):
            self._checkout_tree(commit["sha"])
            self.commit(commit["message"])
    
    def clone(self, source_path: str, dest_path: str):
        """Clone un dépôt local."""
        source = Path(source_path)
        dest = Path(dest_path)
        
        if not (source / ".git").exists():
            raise ValueError(f"{source_path} n'est pas un dépôt Git")
        
        # Créer le répertoire de destination s'il n'existe pas
        dest.mkdir(parents=True, exist_ok=True)
        
        # Si .git existe déjà dans la destination, le supprimer
        dest_git = dest / ".git"
        if dest_git.exists():
            shutil.rmtree(dest_git)
        
        # Copier le dépôt .git
        shutil.copytree(source / ".git", dest_git)
        
        # Créer une nouvelle instance pour le dépôt cloné
        new_repo = TrueGit(str(dest))
        head_commit = new_repo._get_head_commit()
        if head_commit:
            new_repo._checkout_tree(head_commit)
    
    def status(self) -> Dict:
        """Affiche le statut du dépôt."""
        head_commit = self._get_head_commit()
        
        modified = []
        untracked = []
        deleted = []
        
        if head_commit:
            head_files = self._get_tree_files(head_commit)
            
            # Vérifier les fichiers du working tree
            current_files = set()
            for item in self.repo_path.rglob('*'):
                if item.is_file() and '.git' not in item.parts:
                    rel_path = str(item.relative_to(self.repo_path))
                    current_files.add(rel_path)
                    current_content = item.read_text(errors='ignore')
                    
                    if rel_path in head_files:
                        if head_files[rel_path] != current_content:
                            modified.append(rel_path)
                    else:
                        untracked.append(rel_path)
            
            # Détecter les fichiers supprimés (dans HEAD mais pas dans working tree)
            for head_file in head_files.keys():
                if head_file not in current_files:
                    deleted.append(head_file)
        else:
            # Pas de HEAD, tous les fichiers sont untracked
            for item in self.repo_path.rglob('*'):
                if item.is_file() and '.git' not in item.parts:
                    rel_path = str(item.relative_to(self.repo_path))
                    untracked.append(rel_path)
        
        return {
            "branch": self._current_branch,
            "head_commit": head_commit,
            "head_commit_short": head_commit[:8] if head_commit else None,
            "modified": sorted(modified),
            "deleted": sorted(deleted),
            "untracked": sorted(untracked)
        }
    
    def cat_file(self, sha1: str) -> Tuple[str, bytes]:
        """Affiche le contenu d'un objet Git."""
        return self._read_object(sha1)
    
    def bisect(self, bad: str, good: str, test_func) -> str:
        """Bisect pour trouver le commit problématique."""
        commits = []
        current = bad
        
        while current:
            commits.append(current)
            commit_info = self._parse_commit(current)
            if current == good:
                break
            current = commit_info.get("parents", [None])[0]
        
        commits.reverse()
        good_idx = 0
        bad_idx = len(commits) - 1
        
        while good_idx < bad_idx - 1:
            mid = (good_idx + bad_idx) // 2
            self._checkout_tree(commits[mid])
            
            if test_func():
                bad_idx = mid
            else:
                good_idx = mid
        
        return commits[bad_idx]
    
    def fetch(self, remote_path: str):
        """Fetch simplifié depuis un dépôt local."""
        remote = Path(remote_path)
        remote_refs = remote / ".git" / "refs" / "heads"
        
        for branch_file in remote_refs.rglob('*'):
            if branch_file.is_file():
                branch_name = str(branch_file.relative_to(remote_refs))
                remote_ref = self.git_dir / "refs" / "remotes" / "origin" / branch_name
                remote_ref.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(branch_file, remote_ref)
    
    def pull(self, remote_path: str, branch_name: Optional[str] = None):
        """Pull simplifié."""
        if branch_name is None:
            branch_name = self._current_branch
        
        self.fetch(remote_path)
        remote_ref = self.git_dir / "refs" / "remotes" / "origin" / branch_name
        
        if remote_ref.exists():
            remote_commit = remote_ref.read_text().strip()
            self.reset(remote_commit, hard=True)
    
    def push(self, remote_path: str, branch_name: Optional[str] = None):
        """Push simplifié vers un dépôt local."""
        if branch_name is None:
            branch_name = self._current_branch
        
        remote = Path(remote_path)
        local_branch = self.git_dir / "refs" / "heads" / branch_name
        remote_branch = remote / ".git" / "refs" / "heads" / branch_name
        
        if not local_branch.exists():
            raise ValueError(f"La branche {branch_name} n'existe pas")
        
        remote_branch.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(local_branch, remote_branch)
        
        local_objects = self.git_dir / "objects"
        remote_objects = remote / ".git" / "objects"
        
        for obj_dir in local_objects.iterdir():
            if obj_dir.is_dir() and len(obj_dir.name) == 2:
                remote_obj_dir = remote_objects / obj_dir.name
                remote_obj_dir.mkdir(exist_ok=True)
                for obj_file in obj_dir.iterdir():
                    shutil.copy(obj_file, remote_obj_dir / obj_file.name)