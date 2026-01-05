import * as core from "./main.js";

window.editorSave = async function () {
    const text = core.textarea.value;
    const currentHash = core.hashContent(text);

    let filename = core.filenameInput.value.trim();
    if (!filename) {
        alert("Veuillez entrer un nom de fichier avant de sauvegarder.");
        return;
    }

    const res = await fetch("/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ autosave: 0, markdown: text, filename }),
    });

    if (res.ok) {
        core.setLastSavedHash(currentHash);
       // core.lastSavedHash = currentHash;   // ← Mise à jour
        core.openFiles[filename] = text;
        core.lastSavedContent = text;   // ← IMPORTANT
        window.updateBacklinks && window.updateBacklinks();
    }
};

document.addEventListener("DOMContentLoaded", () => {
    async function autoSave() {
        const text = core.textarea.value;
        const currentHash = core.hashContent(text);

        // 🔥 Si rien n’a changé → on ne sauvegarde pas
        if (currentHash === core.lastSavedHash) {
            //console.log("Aucune modification détectée",currentHash," ",core.lastSavedHash);
            return;
            }

        let filename = core.filenameInput.value.trim();
        if (!filename) {
            alert("Veuillez entrer un nom de fichier et le sauvegarder.");
            return;
        }

        if (text === core.lastSavedContent) return; // ← maintenant ça marche

        const res = await fetch("/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ autosave: 1, markdown: text, filename }),
        });

        if (res.ok) {
            core.setLastSavedHash(currentHash);
            //core.lastSavedHash = currentHash;   // ← Mise à jour
            core.openFiles[filename] = text;
            core.lastSavedContent = text; // ← MAJ correcte
            window.updateBacklinks && window.updateBacklinks();
        }
    }

    setInterval(autoSave, 8000);
});

