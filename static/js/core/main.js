// Configuration des features
export const config = {
  enableMinimap: true,
  enableTOC: true,
  enableBacklinks: true,
  enableAutocomplete: true,
  enablePalette: true,
  enableEmojis: true,
  enableMediaPanel: true,
  enableShortcuts: true,
};

export const textarea = document.getElementById("md-input");
export const preview = document.getElementById("preview-content");
export const filenameInput = document.getElementById("filename");
export const tabs = document.getElementById("tabs");
export const explorer = document.getElementById("file-explorer");

export let openFiles = {};
export let lastSavedContent = "";
export let lineNumbersEnabled = false;
export let timeoutId = null;
export let lastSavedHash = 0;

import "./editor.js";
import "./preview.js";
import "./autosave.js";
import "./tabs.js";
import "./explorer.js";
import "../ui/toolbar.js";
import "../ui/splitter.js";
import "../ui/lineNumbers.js";
import "../ui/highlightLine.js";

export function hashContent(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) {
        h = (h * 31 + str.charCodeAt(i)) >>> 0;
    }
    return h;
}
export function setLastSavedHash(h) {
    lastSavedHash = h;
}

// Quand l’éditeur est prêt :
lastSavedHash = hashContent(textarea.value);

// Chargement dynamique des features
async function loadFeature(path) {
  return import(path);
}

async function initFeatures() {
  if (config.enableAutocomplete)
    await loadFeature("/static/js/features/autocomplete.js");

  if (config.enableMinimap)
    await loadFeature("/static/js/features/minimap.js");

  if (config.enableTOC)
    await loadFeature("/static/js/features/toc.js");

  if (config.enableBacklinks)
    await loadFeature("/static/js/features/backlinks.js");

  if (config.enablePalette)
    await loadFeature("/static/js/features/palette.js");

  if (config.enableEmojis) {
    await loadFeature("/static/js/features/emojis.js");
    await loadFeature("/static/js/features/gifs.js");
  }

  if (config.enableMediaPanel)
    await loadFeature("/static/js/features/mediaPanel.js");

  if (config.enableShortcuts)
    await loadFeature("/static/js/shortcuts/shortcuts.js");
}

initFeatures();

// Boutons principaux
document.getElementById("reload-btn").onclick = () => location.reload();
document.getElementById("save-btn").onclick = () => window.editorSave && window.editorSave();

document.addEventListener("DOMContentLoaded", () => {
    window.updatePreview && window.updatePreview();
});


// Init onglet initial
(function init() {
  const name = filenameInput.value;
  if (name) {
    openFiles[name] = textarea.value;
    window.activateTab && window.activateTab(name);
  } else {
    window.updatePreview && window.updatePreview();
  }
})();
