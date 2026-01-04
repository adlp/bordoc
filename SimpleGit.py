#from __future__ import annotations

#import os
#from contextlib import contextmanager
#from dataclasses import dataclass
#from pathlib import Path
#from typing import Any, Dict, Optional

#from dulwich import porcelain
#from dulwich.repo import Repo
#from dulwich.objects import Commit

from truegit import TrueGit
from pathlib import Path

from typing import Any, Dict, Optional
from dataclasses import dataclass

#from typing import List, Dict, Optional
#from datetime import datetime



@dataclass
class SimpleGitResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class SimpleGit:
    #def __init__(self, repo_path: str | Path, default_branch: str = "main"):
    def __init__(self, repo_path: str, default_branch: str = "main"):
        self.repo_path=repo_path
        self.repo=TrueGit(repo_path,default_branch)
        self.default_branch=default_branch
        if len(self.repo.get_commit()) == 0:
            print('Initialisation Simple du repo')
            self.repo.commit(message="Init repo", author="SimpleGit <None>")
            self.repo.create_branch(default_branch)
        print(self.repo.status())
    
    # ------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------
    def write(
        self,
        filename: str,
        content: str,
        branch: Optional[str] = "main",
        message: str = "update",
        author: str = "simplegit <local>",
        encoding="utf-8",
    ) -> SimpleGitResult:
 
        if not branch:
            branch=self.default_branch
        msg="Je ne sais quoi dire"
        commit_sha=0
        # Sauvegarder la branche courante
        original_branch = self.repo.current_branch()
        
        try:
            # Basculer sur la branche cible
            # Si la branche n'existe pas, la créer
            try:
                self.repo.switch(branch)
            except ValueError:
                # La branche n'existe pas, la créer
                #commit_sha = self.repo.commit(message=message, author=author)
                self.repo.create_branch(branch)
                self.repo.switch(branch)
            
            # Créer ou mettre à jour le fichier
            file_path = Path(self.repo_path) / filename
            old_content=self.read(filename,branch,encoding).data.get('content',None)
            if old_content != content:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                file_path.read_text()
            
                # Ajouter à l'index et commiter
                self.repo.add(filename)
                commit_sha = self.repo.commit(message=f'[{filename}] {message}"', author=author)
            
                msg=f"✅ Commit {commit_sha[:8]} créé dans la branche '{branch}'"
            else:
                msg=f"✅ Commit {filename} deja a jour dans la branche '{branch}'"
            
        finally:
            # Toujours revenir à la branche d'origine
            if self.repo.current_branch() != original_branch:
                self.repo.switch(original_branch)
                msg=f"🔄 Retour sur la branche '{original_branch}'"

        print(self.repo.status())
        return SimpleGitResult(
                commit_sha != 0,msg,
                data={"file": filename, "commit": commit_sha, "branch": branch},
                )


    def delete(self, repo_path: str, filename: str, branch: Optional[str]=None, 
                              message: str = "delete", author: str = "simplegit <local>", killbranch: bool = False) -> bool:
        """
        Supprime un fichier dans une branche spécifique et commite l'opération.
        Si la branche devient vide après la suppression, elle peut être supprimée.
        
        Args:
            repo_path: Chemin du dépôt
            filename: Nom du fichier à supprimer
            branch: Branche cible
            message: Message du commit
            author: Auteur du commit
            killbranch: Si True, supprime la branche si elle devient vide (défaut: True)
        
        Returns:
            bool: True si le fichier a été supprimé avec succès, False sinon
        """
        original_branch = self.repo.current_branch()
        branch_deleted = False
        if not branch:
            branch=self.default_branch
        if killbranch and branche == self.default_branch:
            killbranch=False
        
        try:
            # Vérifier si la branche existe
            try:
                self.repo.switch(branch)
            except ValueError:
                print(f"❌ La branche '{branch}' n'existe pas")
                # Créer un commit vide pour documenter l'échec
                error_message = f"Tentative échouée: branche '{branch}' introuvable"
                (Path(self.repo_path) / ".gitkeep").write_text("")
                self.repo.add(".gitkeep")
                commit=self.repo.commit(message=error_message, author=author)
                return SimpleGitResult(
                        False,error_message,
                        data={"file": filename, "commit": commit, "branch": branch},
                        )
            
            # Vérifier si le fichier existe
            file_path = Path(self.repo_path) / filename
            if not file_path.exists():
                print(f"❌ Le fichier '{filename}' n'existe pas dans la branche '{branch}'")
                # Créer un commit vide pour documenter l'échec
                error_message = f"Tentative échouée: fichier '{filename}' introuvable dans '{branch}'"
                (Path(self.repo_path) / ".gitkeep").write_text("")
                self.repo.add(".gitkeep")
                commit=self.repo.commit(message=error_message, author=author)
                return SimpleGitResult(
                        False,error_message,
                        data={"file": filename, "commit": commit, "branch": branch},
                        )
            
            # Supprimer le fichier
            file_path.unlink()
            print(f"✅ Fichier '{filename}' supprimé")
            
            # Compter les fichiers restants (hors .git)
            remaining_files = []
            for item in Path(self.repo_path).rglob('*'):
                if item.is_file() and '.git' not in item.parts:
                    remaining_files.append(item)
            
            # Si la branche devient vide et killbranch est activé
            if len(remaining_files) == 0 and killbranch:
                print(f"⚠️  La branche '{branch}' est maintenant vide")
                
                # Retourner sur la branche d'origine avant de supprimer
                if branch != original_branch:
                    self.repo.switch(original_branch)
                    print(f"🔄 Retour sur la branche '{original_branch}'")
                else:
                    # Si on supprime la branche courante, basculer sur main
                    try:
                        self.repo.switch("main")
                        original_branch = "main"
                        print(f"🔄 Basculement sur 'main' (branche par défaut)")
                    except:
                        # Si main n'existe pas, créer une branche temporaire
                        branches = self.repo.list_branches()
                        branch_names = [b.strip().lstrip('* ') for b in branches]
                        other_branches = [b for b in branch_names if b != branch]
                        if other_branches:
                            self.repo.switch(other_branches[0])
                            original_branch = other_branches[0]
                            print(f"🔄 Basculement sur '{other_branches[0]}'")
                
                # Supprimer la branche vide
                self.repo.delete_branch(branch)
                branch_deleted = True
                print(f"🗑️  Branche '{branch}' supprimée (vide)")
                
                # Créer un commit pour documenter la suppression
                (Path(self.repo_path) / ".gitkeep").write_text("")
                self.repo.add(".gitkeep")
                commit_msg = f"Branch '{branch}' deleted: {message} (branch was empty)"
                commit=self.repo.commit(message=commit_msg, author=author)
                return SimpleGitResult(
                        True,commit_msg,
                        data={"file": filename, "commit": commit, "branch": branch},
                        )
            
            # Sinon, commiter normalement la suppression
            # Ajouter tous les fichiers restants pour recréer le tree
            for item in remaining_files:
                rel_path = str(item.relative_to(self.repo_path))
                self.repo.add(rel_path)
            
            # Commiter la suppression
            commit_sha = self.repo.commit(message=message, author=author)
            print(f"✅ Commit {commit_sha[:8]}: {message}")
            print(f"📊 {len(remaining_files)} fichier(s) restant(s) dans la branche")
            
            return SimpleGitResult(
                    True,message,
                    data={"file": filename, "commit": commit_sha, "branch": branch},
                    )
            
        except Exception as e:
            error_message=f"❌ Erreur inattendue: {e}"
            print(error_message)
            # Créer un commit pour documenter l'erreur
            try:
                error_message = f"Erreur lors de la suppression de '{filename}': {str(e)}"
                (Path(slef.repo_path) / ".gitkeep").write_text("")
                self.repo.add(".gitkeep")
                commit_sha=self.repo.commit(message=error_message, author=author)
            except:
                pass
            return SimpleGitResult(
                    False,error_message,
                    data={"file": filename, "commit": commit_sha, "branch": branch},
                    )
            
        finally:
            # Toujours revenir à la branche d'origine (si elle existe encore)
            current = self.repo.current_branch()
            if not branch_deleted and current != original_branch:
                try:
                    self.repo.switch(original_branch)
                    msg=f"🔄 Retour sur la branche '{original_branch}'"
                except Exception as e:
                    msg=f"⚠️  Impossible de revenir sur '{original_branch}': {e}"
            elif branch_deleted and current != original_branch:
                msg=f"ℹ️  Branche supprimée, resté sur '{current}'"
            print(msg)

            return SimpleGitResult(
                    False,msg,
                    data={"file": filename, "commit": 0, "branch": branch},
                    )

    def read(self, filename: str,branch:str=None,encoding="utf-8") -> SimpleGitResult:
        msg="Rien a dire"
        original_branch = self.repo.current_branch()
        content=None
        statut=True
        if not branch:
            branch=self.default_branch
        try:
            self.repo.switch(branch)
        except ValueError:
            # La branche n'existe pas, on meurre proprement
            msg="Pas de branche"
            content=None
            statut=False
        if statut:
            filename = filename.strip("/")
            full_path = (Path(self.repo_path) / filename).resolve()

            statut=False
            try:
                # Vérifier que ce n'est pas un répertoire
                if full_path.is_dir():
                    msg=f"Erreur: '{full_path}' est un répertoire, pas un fichier."
                else:
                    # Ouvrir et lire le fichier
                    content=full_path.read_text()
                    #with full_path.open("r", encoding=encoding) as f:
                    #    content=f.read()
                    msg=f"Le fichier '{full_path}' a ete lut."
                    statut=True
        
            except FileNotFoundError:
                msg=f"Erreur: le fichier '{full_path}' n'existe pas."
            except PermissionError:
                msg=f"Erreur: permission refusée pour lire '{full_path}'."
            except IsADirectoryError:
                msg=f"Erreur: '{full_path}' est un répertoire, pas un fichier."
            except OSError as e:
                # Erreurs d'E/S diverses
                msg=f"Erreur d'E/S en lisant '{full_path}': {e}"
            
        if self.repo.current_branch() != original_branch:
            self.repo.switch(original_branch)
        return SimpleGitResult(statut , msg,
            data={"file": filename, "content": content })
            #full_path.read_text(encoding="utf-8")})


    def ls(self, directory: str = "",branch:str ="main") -> SimpleGitResult:
        """
        Liste les fichiers et répertoires dans une branche avec leurs métadonnées Git.
        
        Args:
            repo_path: Chemin du dépôt
            branch: Branche à explorer
            directory: Sous-répertoire à lister (vide = racine)
        
        Returns:
            Liste de dictionnaires contenant:
            - name: Nom du fichier/répertoire
            - type: 'file' ou 'directory'
            - last_commit_sha: SHA du dernier commit ayant modifié cet élément
            - last_commit_date: Date du dernier commit (timestamp)
            - last_commit_author: Auteur du dernier commit
            - last_commit_message: Message du dernier commit
            - path: Chemin complet relatif
        """
        original_branch = self.repo.current_branch()
        
        try:
            # Basculer sur la branche demandée
            try:
                self.repo.switch(branch)
            except ValueError:
                raise ValueError(f"La branche '{branch}' n'existe pas")
            
            # Normaliser le chemin du répertoire
            if directory:
                directory = directory.strip("/")
                target_path = Path(self.repo_path) / directory
                if not target_path.exists() or not target_path.is_dir():
                    raise ValueError(f"Le répertoire '{directory}' n'existe pas")
            else:
                target_path = Path(self.repo_path)
            
            # Récupérer l'historique complet
            commits = self.repo.log()
            
            # Construire un cache des dernières modifications pour chaque fichier
            file_last_commit = {}
            
            for commit in commits:
                commit_sha = commit['sha']
                commit_info = self.repo._parse_commit(commit_sha)
                
                # Récupérer les fichiers de ce commit
                try:
                    files = self.repo._get_tree_files(commit_sha)
                    
                    # Pour chaque fichier, si on ne l'a pas encore vu, c'est son dernier commit
                    for filepath in files.keys():
                        if filepath not in file_last_commit:
                            file_last_commit[filepath] = {
                                'sha': commit_sha,
                                'author': commit_info['author'],
                                'message': commit_info['message'],
                                'date': commit_info['committer'].split()[-2]  # Extraire timestamp
                            }
                except:
                    continue
            
            # Construire un cache pour les répertoires
            # Un répertoire hérite de la date du fichier le plus récent qu'il contient
            dir_last_commit = {}
            
            for filepath, commit_data in file_last_commit.items():
                parts = Path(filepath).parts
                # Pour chaque niveau de répertoire parent
                for i in range(len(parts)):
                    dir_path = str(Path(*parts[:i+1]).parent) if i > 0 else ""
                    if dir_path not in dir_last_commit:
                        dir_last_commit[dir_path] = commit_data
                    else:
                        # Garder le commit le plus récent
                        if int(commit_data['date']) > int(dir_last_commit[dir_path]['date']):
                            dir_last_commit[dir_path] = commit_data
            
            # Lister les éléments du répertoire
            results = []
            seen_names = set()
            
            # Lister les fichiers et répertoires physiques
            for item in sorted(target_path.iterdir()):
                if item.name == ".git":
                    continue
                
                seen_names.add(item.name)
                
                # Construire le chemin relatif
                if directory:
                    rel_path = str(Path(directory) / item.name)
                else:
                    rel_path = item.name
                
                item_type = "directory" if item.is_dir() else "file"
                
                # Trouver les informations du dernier commit
                if item_type == "file":
                    commit_data = file_last_commit.get(rel_path, None)
                else:
                    # Pour un répertoire, chercher dans le cache
                    commit_data = dir_last_commit.get(rel_path, None)
                    
                    # Si pas trouvé, chercher le fichier le plus récent dans ce répertoire
                    if not commit_data:
                        most_recent = None
                        for filepath, data in file_last_commit.items():
                            if filepath.startswith(rel_path + "/"):
                                if most_recent is None or int(data['date']) > int(most_recent['date']):
                                    most_recent = data
                        commit_data = most_recent
                
                if commit_data:
                    results.append({
                        'name': item.name,
                        'type': item_type,
                        'path': rel_path,
                        'last_commit_sha': commit_data['sha'],
                        'last_commit_date': int(commit_data['date']),
                        'last_commit_author': commit_data['author'],
                        'last_commit_message': commit_data['message']
                    })
                else:
                    # Fichier sans historique (non commité)
                    results.append({
                        'name': item.name,
                        'type': item_type,
                        'path': rel_path,
                        'last_commit_sha': None,
                        'last_commit_date': None,
                        'last_commit_author': None,
                        'last_commit_message': "Non commité"
                    })
            
            return results
            
        finally:
            # Toujours revenir à la branche d'origine
            if self.repo.current_branch() != original_branch:
                try:
                    self.repo.switch(original_branch)
                except:
                    pass 

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

