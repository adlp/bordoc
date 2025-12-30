import * as core from "../core/main.js";

window.updateTOC = function () {
    const tocList = document.getElementById("toc-list");
    tocList.innerHTML = "";

    const container = document.createElement("div");
    container.innerHTML = core.preview.innerHTML;

    const headings = container.querySelectorAll("h1,h2,h3,h4,h5,h6");

    headings.forEach((h, index) => {
        const level = parseInt(h.tagName.substring(1), 10);
        const text = h.textContent.trim();
        if (!text) return;

        const id = h.id || "toc-" + index;

        const realHeadings = core.preview.querySelectorAll(h.tagName);
        const realHeading = realHeadings[index];
        if (realHeading && !realHeading.id) realHeading.id = id;

        const li = document.createElement("li");
        const span = document.createElement("span");
        span.textContent = text;
        span.className = "toc-level-" + level;
        span.onclick = () => {
            const target = document.getElementById(id);
            if (target) {
                const top = target.offsetTop;
                document.getElementById("preview").scrollTo({ top, behavior: "smooth" });
            }
        };
        li.appendChild(span);
        tocList.appendChild(li);
    });
};
