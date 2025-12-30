import { explorer } from "./main.js";

const fileList = document.getElementById("file-list");

async function loadFiles() {
  const res = await fetch("/listefichiers");
  const data = await res.json();
  fileList.innerHTML = "";
  data.files.forEach(f => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.textContent = f;
    a.onclick = (e) => {
      e.preventDefault();
      loadFile(f);
    };
    li.appendChild(a);
    fileList.appendChild(li);
  });
}

async function loadFile(filename) {
  const res = await fetch("/read/" + encodeURIComponent(filename));
  const data = await res.json();
  window.openTab && window.openTab(filename, data.content);
}

window.toggleExplorer = function() {
  const visible = explorer.style.display === "block";
  explorer.style.display = visible ? "none" : "block";
  if (!visible) loadFiles();
};

document.querySelector('[data-action="toggle-explorer"]').onclick = () => window.toggleExplorer();

