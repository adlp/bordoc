import { textarea, preview } from "../core/main.js";

const acMenu = document.getElementById("autocomplete-menu");
let acItems = [];
let acIndex = -1;

function showAutocomplete(items, x, y) {
  acMenu.innerHTML = "";
  acItems = items;
  acIndex = -1;
  items.forEach((item, i) => {
    const div = document.createElement("div");
    div.className = "autocomplete-item";
    div.textContent = item.label;
    div.onclick = () => applyAutocomplete(i);
    acMenu.appendChild(div);
  });
  acMenu.style.left = x + "px";
  acMenu.style.top = y + "px";
  acMenu.style.display = "block";
}

function hideAutocomplete() {
  acMenu.style.display = "none";
  acItems = [];
  acIndex = -1;
}

function applyAutocomplete(i) {
  const item = acItems[i];
  if (!item) return;
  const pos = textarea.selectionStart;
  const before = textarea.value.substring(0, pos - item.trigger.length);
  const after = textarea.value.substring(pos);
  textarea.value = before + item.insert + after;
  textarea.selectionStart = textarea.selectionEnd = before.length + item.insert.length;
  hideAutocomplete();
  window.updatePreview && window.updatePreview();
}

textarea.addEventListener("keyup", async (e) => {
  const pos = textarea.selectionStart;
  const text = textarea.value.substring(0, pos);
  const rect = textarea.getBoundingClientRect();
  const x = rect.left + 40;
  const y = rect.top + textarea.scrollTop + 60;

  if (text.endsWith("![")) {
    const res = await fetch("/listemedias");
    const data = await res.json();
    const imgs = (data.medias || []).filter(f => /\.(png|jpg|jpeg|gif|webp)$/i.test(f));
    showAutocomplete(imgs.map(f => ({
      label: f,
      insert: `![${f}](/medias/${f})`,
      trigger: "!["
    })), x, y);
    return;
  }

  if (text.endsWith("[")) {
    const res = await fetch("/listefichiers");
    const data = await res.json();
    showAutocomplete(data.files.map(f => ({
      label: f,
      insert: `[${f}](${f})`,
      trigger: "["
    })), x, y);
    return;
  }

  if (text.endsWith("#")) {
    const headings = [...preview.querySelectorAll("h1,h2,h3,h4,h5,h6")].map(h => h.textContent.trim());
    showAutocomplete(headings.map(h => ({
      label: h,
      insert: h,
      trigger: "#"
    })), x, y);
    return;
  }

  hideAutocomplete();
});

document.addEventListener("keydown", (e) => {
  if (acItems.length === 0) return;
  const items = [...acMenu.children];

  if (e.key === "ArrowDown") {
    e.preventDefault();
    acIndex = (acIndex + 1) % acItems.length;
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    acIndex = (acIndex - 1 + acItems.length) % acItems.length;
  } else if (e.key === "Enter") {
    e.preventDefault();
    applyAutocomplete(acIndex);
  } else if (e.key === "Escape") {
    hideAutocomplete();
  }

  items.forEach((c, i) => c.classList.toggle("active", i === acIndex));
});

