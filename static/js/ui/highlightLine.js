import * as core from "../core/main.js";

document.addEventListener("DOMContentLoaded", () => {
    const textarea = core.textarea;
    const minimapContent = document.getElementById("minimap-content");

    function highlightActiveLine() {
        const textBefore = textarea.value.substr(0, textarea.selectionStart);
        const lineIndex = textBefore.split("\n").length - 1;
        const lines = textarea.value.split("\n");

        let html = "";
        for (let i = 0; i < lines.length; i++) {
            const safe = lines[i].replace(/</g, "&lt;").replace(/>/g, "&gt;");
            if (i === lineIndex) {
                html += `<div class="active-line-highlight">${safe}</div>\n`;
            } else {
                html += `<div>${safe}</div>\n`;
            }
        }
        minimapContent.innerHTML = html;
    }

    textarea.addEventListener("keyup", highlightActiveLine);
    textarea.addEventListener("click", highlightActiveLine);
    textarea.addEventListener("input", highlightActiveLine);
});

