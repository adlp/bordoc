document.addEventListener("keydown", function(e) {
  // Ctrl + S → sauvegarde
  if (e.ctrlKey && e.key.toLowerCase() === "s") {
    e.preventDefault();
    window.editorSave && window.editorSave();
    return;
  }

  // Ctrl + B → gras
  if (e.ctrlKey && e.key.toLowerCase() === "b") {
    e.preventDefault();
    window.wrap && window.wrap("**", "**");
    return;
  }

  // Ctrl + I → italique
  if (e.ctrlKey && e.key.toLowerCase() === "i") {
    e.preventDefault();
    window.wrap && window.wrap("*", "*");
    return;
  }

  // Ctrl + U → souligner
  if (e.ctrlKey && e.key.toLowerCase() === "u") {
    e.preventDefault();
    window.wrap && window.wrap("<u>", "</u>");
    return;
  }

  // Ctrl + L → liste
  if (e.ctrlKey && e.key.toLowerCase() === "l") {
    e.preventDefault();
    window.insertTextAtCursor && window.insertTextAtCursor("- ");
    return;
  }

  // Ctrl + H → titre H1
  if (e.ctrlKey && e.key.toLowerCase() === "h") {
    e.preventDefault();
    window.insertTextAtCursor && window.insertTextAtCursor("# ");
    return;
  }

  // Ctrl + M → panneau médias
  if (e.ctrlKey && e.key.toLowerCase() === "m") {
    e.preventDefault();
    window.openMediaPanel && window.openMediaPanel();
    return;
  }

  // Ctrl + / → citation
  if (e.ctrlKey && e.key === "/") {
    e.preventDefault();
    window.wrap && window.wrap("> ", "");
    return;
  }
});

