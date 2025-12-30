const palette = document.getElementById("command-palette");
const paletteInput = document.getElementById("command-input");
const paletteResults = document.getElementById("command-results");

let paletteCommands = [
  { label: "Gras", action: () => window.wrap("**","**") },
  { label: "Italique", action: () => window.wrap("*","*") },
  { label: "Souligner", action: () => window.wrap("<u>","</u>") },
  { label: "Titre H1", action: () => window.insertTextAtCursor("# ") },
  { label: "Titre H2", action: () => window.insertTextAtCursor("## ") },
  { label: "Titre H3", action: () => window.insertTextAtCursor("### ") },
  { label: "Liste", action: () => window.insertTextAtCursor("- ") },
  { label: "Citation", action: () => window.wrap("> ","") },
  { label: "Ouvrir médias", action: () => window.openMediaPanel && window.openMediaPanel() },
  { label: "Sauvegarder", action: () => window.editorSave && window.editorSave() },
];

let paletteIndex = -1;

window.openPalette = function() {
  palette.style.display = "block";
  paletteInput.value = "";
  paletteInput.focus();
  updatePaletteResults("");
};

function closePalette() {
  palette.style.display = "none";
}

function updatePaletteResults(query) {
  paletteResults.innerHTML = "";
  const filtered = paletteCommands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()));
  filtered.forEach((cmd) => {
    const div = document.createElement("div");
    div.className = "command-item";
    div.textContent = cmd.label;
    div.onclick = () => {
      cmd.action();
      closePalette();
    };
    paletteResults.appendChild(div);
  });
  paletteIndex = -1;
}

paletteInput.addEventListener("input", () => {
  updatePaletteResults(paletteInput.value);
});

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "p") {
    e.preventDefault();
    window.openPalette();
    return;
  }

  if (palette.style.display === "block") {
    const items = [...paletteResults.children];
    if (e.key === "Escape") {
      closePalette();
      return;
    }
    if (items.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteIndex = (paletteIndex + 1) % items.length;
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteIndex = (paletteIndex - 1 + items.length) % items.length;
    } else if (e.key === "Enter") {
      e.preventDefault();
      const label = items[paletteIndex]?.textContent;
      const cmd = paletteCommands.find(c => c.label === label);
      if (cmd) cmd.action();
      closePalette();
    }
    items.forEach((el, i) => el.classList.toggle("active", i === paletteIndex));
  }
});

