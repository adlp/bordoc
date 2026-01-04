import os
import hashlib
import zlib
import time
from pathlib import Path
from typing import Optional, List, Dict
import stat


class TrueGit:
    """Implémentation pure Python d'un client Git compatible avec les dépôts Git standard."""
    
    def __init__(self, repo_path: str, branch: str = "main"):
        """
        Initialise un dépôt Git.
        
        Args:
            repo_path: Chemin du dépôt sur le disque
            branch: Nom de la branche (par défaut: main)
        """
        self.repo_path = Path(repo_path).absolute()
        self.git_dir = self.repo_path / ".git"
        self.branch = branch
        
        if not self.git_dir.exists():
            self._init_repository()
        
    def _init_repository(self):
        """Initialise la structure du dépôt Git."""
        # Créer les répertoires nécessaires
        dirs = [
            self.git_dir,
            self.git_dir / "objects",
            self.git_dir / "refs" / "heads",
            self.git_dir / "refs" / "tags",
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        
        # Créer HEAD
        head_file = self.git_dir / "HEAD"
        head_file.write_text(f"ref: refs/heads/{self.branch}\n")
        
        # Créer le fichier de config
        config_file = self.git_dir / "config"
        config_file.write_text("[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n")
        
    def _hash_object(self, data: bytes, obj_type: str) -> str:
        """
        Hash un objet Git et le stocke.
        
        Args:
            data: Contenu de l'objet
            obj_type: Type d'objet (blob, tree, commit)
            
        Returns:
            SHA-1 de l'objet
        """
        # Créer l'en-tête
        header = f"{obj_type} {len(data)}\0".encode()
        store = header + data
        
        # Calculer le SHA-1
        sha1 = hashlib.sha1(store).hexdigest()
        
        # Créer le chemin de stockage
        obj_dir = self.git_dir / "objects" / sha1[:2]
        obj_dir.mkdir(exist_ok=True)
        obj_file = obj_dir / sha1[2:]
        
        # Compresser et stocker
        if not obj_file.exists():
            compressed = zlib.compress(store)
            obj_file.write_bytes(compressed)
        
        return sha1
    
    def _read_object(self, sha1: str) -> tuple[str, bytes]:
        """
        Lit un objet Git depuis le dépôt.
        
        Args:
            sha1: Hash de l'objet
            
        Returns:
            Tuple (type, contenu)
        """
        obj_file = self.git_dir / "objects" / sha1[:2] / sha1[2:]
        
        if not obj_file.exists():
            raise ValueError(f"Objet {sha1} introuvable")
        
        # Décompresser
        compressed = obj_file.read_bytes()
        data = zlib.decompress(compressed)
        
        # Séparer l'en-tête du contenu
        null_idx = data.index(b'\0')
        header = data[:null_idx].decode()
        content = data[null_idx + 1:]
        
        obj_type = header.split()[0]
        
        return obj_type, content
    
    def _create_tree_from_index(self, path: Path = None) -> str:
        """
        Crée un objet tree à partir des fichiers du répertoire.
        
        Args:
            path: Chemin du répertoire (par défaut: repo_path)
            
        Returns:
            SHA-1 de l'arbre
        """
        if path is None:
            path = self.repo_path
        
        entries = []
        
        for item in sorted(path.iterdir()):
            if item.name == ".git":
                continue
            
            if item.is_file():
                # Créer un blob pour le fichier
                content = item.read_bytes()
                sha1 = self._hash_object(content, "blob")
                mode = "100644"  # Fichier normal
                if os.access(item, os.X_OK):
                    mode = "100755"  # Fichier exécutable
                
                entries.append((mode, item.name, sha1))
            
            elif item.is_dir():
                # Créer récursivement un tree pour le sous-répertoire
                sha1 = self._create_tree_from_index(item)
                mode = "40000"  # Répertoire
                
                entries.append((mode, item.name, sha1))
        
        # Créer le contenu du tree
        tree_content = b""
        for mode, name, sha1 in entries:
            tree_content += f"{mode} {name}\0".encode()
            tree_content += bytes.fromhex(sha1)
        
        return self._hash_object(tree_content, "tree")
    
    def commit(self, message: str, author: Optional[str] = None, 
               committer: Optional[str] = None, date: Optional[int] = None) -> str:
        """
        Crée un commit.
        
        Args:
            message: Message du commit
            author: Auteur (format: "Nom <email>")
            committer: Committeur (format: "Nom <email>")
            date: Timestamp Unix (par défaut: maintenant)
            
        Returns:
            SHA-1 du commit
        """
        # Valeurs par défaut
        if author is None:
            author = "TrueGit User <truegit@example.com>"
        if committer is None:
            committer = author
        if date is None:
            date = int(time.time())
        
        # Créer l'arbre
        tree_sha = self._create_tree_from_index()
        
        # Récupérer le commit parent
        parent_sha = self._get_head_commit()
        
        # Créer le contenu du commit
        commit_content = f"tree {tree_sha}\n"
        if parent_sha:
            commit_content += f"parent {parent_sha}\n"
        commit_content += f"author {author} {date} +0000\n"
        commit_content += f"committer {committer} {date} +0000\n"
        commit_content += f"\n{message}\n"
        
        # Hasher et stocker le commit
        commit_sha = self._hash_object(commit_content.encode(), "commit")
        
        # Mettre à jour la référence de branche
        branch_file = self.git_dir / "refs" / "heads" / self.branch
        branch_file.write_text(f"{commit_sha}\n")
        
        return commit_sha
    
    def _get_head_commit(self) -> Optional[str]:
        """Récupère le SHA-1 du commit HEAD."""
        branch_file = self.git_dir / "refs" / "heads" / self.branch
        
        if not branch_file.exists():
            return None
        
        return branch_file.read_text().strip()
    
    def log(self, max_count: Optional[int] = None) -> List[Dict]:
        """
        Affiche l'historique des commits.
        
        Args:
            max_count: Nombre maximum de commits à afficher
            
        Returns:
            Liste de dictionnaires contenant les informations des commits
        """
        commits = []
        current_sha = self._get_head_commit()
        count = 0
        
        while current_sha and (max_count is None or count < max_count):
            obj_type, content = self._read_object(current_sha)
            
            if obj_type != "commit":
                break
            
            # Parser le commit
            lines = content.decode().split('\n')
            commit_info = {"sha": current_sha}
            
            for line in lines:
                if line.startswith("tree "):
                    commit_info["tree"] = line.split()[1]
                elif line.startswith("parent "):
                    commit_info["parent"] = line.split()[1]
                    current_sha = commit_info["parent"]
                elif line.startswith("author "):
                    commit_info["author"] = line[7:]
                elif line.startswith("committer "):
                    commit_info["committer"] = line[10:]
                elif line == "":
                    # Le message commence après la ligne vide
                    idx = content.decode().index('\n\n')
                    commit_info["message"] = content.decode()[idx+2:].strip()
                    break
            
            commits.append(commit_info)
            count += 1
            
            if "parent" not in commit_info:
                break
        
        return commits
    
    def cat_file(self, sha1: str) -> tuple[str, bytes]:
        """
        Affiche le contenu d'un objet Git.
        
        Args:
            sha1: Hash de l'objet
            
        Returns:
            Tuple (type, contenu)
        """
        return self._read_object(sha1)
    
    def status(self) -> Dict:
        """
        Affiche le statut du dépôt.
        
        Returns:
            Dictionnaire avec les informations de statut
        """
        head_commit = self._get_head_commit()
        
        return {
            "branch": self.branch,
            "head_commit": head_commit,
            "repo_path": str(self.repo_path)
        }