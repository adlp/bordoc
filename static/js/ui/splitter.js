const splitter = document.getElementById("splitter");
const editor = document.getElementById("editor");
const explorer = document.getElementById("file-explorer");
const tocPanel = document.getElementById("toc-panel");

let dragging = false;
splitter.addEventListener("mousedown", () => dragging = true);
document.addEventListener("mouseup", () => dragging = false);

document.addEventListener("mousemove", (e) => {
  if (!dragging) return;

  const explorerWidth = (explorer.style.display === "block") ? explorer.offsetWidth : 0;
  const tocWidth = tocPanel.offsetWidth;
  const offsetLeft = explorerWidth + tocWidth;
  const newEditorWidth = e.clientX - offsetLeft;
  if (newEditorWidth < 150) return;

  editor.style.flex = "none";
  editor.style.width = newEditorWidth + "px";
});

