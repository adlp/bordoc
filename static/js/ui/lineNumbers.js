import * as core from "../core/main.js";

window.toggleLineNumbers = function () {
    const ln = document.getElementById("line-numbers");
    ln.classList.toggle("active");
    window.updateLineNumbers();
};

window.updateLineNumbers = function () {
    const ln = document.getElementById("line-numbers");
    if (!ln.classList.contains("active")) return;

    const textarea = core.textarea;
    const lines = textarea.value.split("\n").length;
    ln.innerHTML = Array.from({ length: lines }, (_, i) => i + 1).join("<br>");
    ln.scrollTop = textarea.scrollTop;
};

document.addEventListener("DOMContentLoaded", () => {
    const textarea = core.textarea;
    const ln = document.getElementById("line-numbers");

    textarea.addEventListener("scroll", () => {
        ln.scrollTop = textarea.scrollTop;
    });
});
