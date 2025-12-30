import { textarea, preview, filenameInput, tabs, openFiles } from "./main.js";

window.openTab = function(filename, content) {
  if (openFiles[filename] !== undefined) {
    window.activateTab(filename);
    return;
  }
  openFiles[filename] = content;

  const tab = document.createElement("div");
  tab.className = "tab";
  tab.dataset.filename = filename;
  tab.innerHTML = `
    <span class="tab-name">${filename}</span>
    <span class="close-tab" onclick="closeTab(event, '${filename}')">✖</span>
  `;
  tab.onclick = () => window.activateTab(filename);
  tabs.appendChild(tab);
  window.activateTab(filename);
};

window.activateTab = function(filename) {
  [...tabs.children].forEach(t => {
    t.classList.toggle("active", t.dataset.filename === filename);
  });
  textarea.value = openFiles[filename];
  filenameInput.value = filename;
  window.updatePreview && window.updatePreview();
  window.updateBacklinks && window.updateBacklinks();
};

window.closeTab = function(event, filename) {
  event.stopPropagation();
  delete openFiles[filename];
  const tab = [...tabs.children].find(t => t.dataset.filename === filename);
  if (tab) tab.remove();

  const remaining = Object.keys(openFiles);
  if (remaining.length > 0) {
    window.activateTab(remaining[0]);
  } else {
    textarea.value = "";
    preview.innerHTML = "";
    filenameInput.value = "";
    window.updateLineNumbers && window.updateLineNumbers();
    document.getElementById("toc-list").innerHTML = "";
    document.getElementById("backlinks-list").innerHTML = "<li>Aucun fichier actif</li>";
    window.updateMinimap && window.updateMinimap();
  }
};

