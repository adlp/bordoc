import * as core from "./main.js";

window.updatePreview = async function () {
  const text = core.textarea.value;

  const res = await fetch("/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown: text }),
  });

  const data = await res.json();

/*
  // 1) enlever les échappements JSON
  const unescaped = data.html
    .replace(/\\"/g, '"')
    .replace(/\\n/g, '\n')
    .replace(/\\\\/g, '\\');

  // 2) injecter
  core.preview.innerHTML = unescaped;
*/
  core.preview.innerHTML = data.html;

  hljs.highlightAll();

  window.updateLineNumbers && window.updateLineNumbers();
  window.updateTOC && window.updateTOC();   // ← IMPORTANT
  window.updateMinimap && window.updateMinimap();
  mermaid.init(undefined, document.querySelectorAll(".mermaid"));
/*
  core.updateLineNumbers && core.updateLineNumbers();
  core.updateTOC && core.updateTOC();
  core.updateMinimap && core.updateMinimap();
*/
};

document.addEventListener("DOMContentLoaded", () => {
  core.textarea.addEventListener("input", () => {
    clearTimeout(window._previewTimeout);
    window._previewTimeout = setTimeout(window.updatePreview, 200);
  });
});
