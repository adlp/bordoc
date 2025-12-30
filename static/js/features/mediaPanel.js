import { textarea } from "../core/main.js";

const mediaPanel = document.getElementById("media-panel");
const mediaList = document.getElementById("media-list");
const mediaDropzone = document.getElementById("media-dropzone");

document.getElementById("media-close").onclick = () => mediaPanel.style.display = "none";

window.openMediaPanel = function() {
  mediaPanel.style.display = "flex";
  loadMediaList();
};

async function loadMediaList() {
  const res = await fetch("/listemedias");
  const data = await res.json();
  mediaList.innerHTML = "";

  if (data.folders) {
    Object.keys(data.folders).forEach(folder => {
      const title = document.createElement("h4");
      title.textContent = folder;
      mediaList.appendChild(title);
      data.folders[folder].forEach(media => {
        renderMediaItem(media, folder);
      });
    });
  }
  if (data.medias) {
    data.medias.forEach(media => renderMediaItem(media, null));
  }
}

function renderMediaItem(media, folder) {
  const ext = media.split('.').pop().toLowerCase();
  const item = document.createElement("div");
  item.className = "media-item";
  const path = folder ? folder + '/' + media : media;

  let preview = "";
  if (["png","jpg","jpeg","gif","webp"].includes(ext)) {
    preview = `<img src="/medias/${path}">`;
  } else if (["mp4","webm","ogg"].includes(ext)) {
    preview = `<video src="/medias/${path}" muted></video>`;
  } else {
    preview = `<span>📄</span>`;
  }

  item.innerHTML = `
    ${preview}
    <span class="media-name">${path}</span>
    <div class="media-actions">
      <button class="rename-btn">✏️</button>
      <button class="delete-btn">🗑️</button>
    </div>
  `;

  item.addEventListener("click", (e) => {
    if (e.target.closest(".media-actions")) return;
    insertMedia(path);
  });

  item.querySelector(".rename-btn").onclick = async (e) => {
    e.stopPropagation();
    const newName = prompt("Nouveau nom :", media);
    if (!newName) return;
    const res = await fetch("/renamemedia", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ old: path, "new": (folder ? folder + '/' : '') + newName })
    });
    if (res.ok) loadMediaList(); else alert("Erreur renommage");
  };

  item.querySelector(".delete-btn").onclick = async (e) => {
    e.stopPropagation();
    if (!confirm("Supprimer ce média ?")) return;
    const res = await fetch("/deletemedia", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ file: path })
    });
    if (res.ok) loadMediaList(); else alert("Erreur suppression");
  };

  mediaList.appendChild(item);
}

function insertMedia(path) {
  const filename = path.split('/').pop();
  const ext = filename.split('.').pop().toLowerCase();
  let insertText = "";
  if (["png","jpg","jpeg","gif","webp"].includes(ext)) {
    insertText = `![${filename}](/medias/${path})`;
  } else if (["mp4","webm","ogg"].includes(ext)) {
    insertText = `<video controls src="/medias/${path}"></video>`;
  } else {
    insertText = `[${filename}](/medias/${path})`;
  }
  const pos = textarea.selectionStart;
  textarea.setRangeText(insertText, pos, pos, "end");
  window.updatePreview && window.updatePreview();
}

// DnD dans panneau médias
mediaDropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  mediaDropzone.classList.add("dragover");
});
mediaDropzone.addEventListener("dragleave", () => {
  mediaDropzone.classList.remove("dragover");
});
mediaDropzone.addEventListener("drop", async (e) => {
  e.preventDefault();
  mediaDropzone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/savemedia", {
    method: "POST",
    body: formData
  });
  if (res.ok) {
    loadMediaList();
    insertMedia(file.name);
  } else {
    alert("Erreur upload média");
  }
});

