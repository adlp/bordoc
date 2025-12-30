import { textarea } from "../core/main.js";

const minimapContent = document.getElementById("minimap-content");

window.updateMinimap = function() {
  const text = textarea.value;
  const lines = text.split("\n").slice(0, 400);
  const html = lines
    .map(l => l.replace(/</g, "&lt;").replace(/>/g, "&gt;"))
    .join("\n");
  minimapContent.innerHTML = html;
};

