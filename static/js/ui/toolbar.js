import { textarea } from "../core/main.js";

const toolbar = document.getElementById("toolbar");

toolbar.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  const action = btn.dataset.action;
  if (!action) return;

  switch (action) {
    case "bold": window.wrap("**","**"); break;
    case "italic": window.wrap("*","*"); break;
    case "strike": window.wrap("~~","~~"); break;
    case "underline": window.wrap("<u>","</u>"); break;
    case "code": window.wrap("`","`"); break;
    case "h1": window.insertTextAtCursor("# "); break;
    case "h2": window.insertTextAtCursor("## "); break;
    case "h3": window.insertTextAtCursor("### "); break;
    case "ul": window.insertTextAtCursor("- "); break;
    case "ol": window.insertTextAtCursor("1. "); break;
    case "quote": window.wrap("> ",""); break;
    case "link": window.wrap("[texte](", ")"); break;
    case "image": window.wrap("![alt](", ")"); break;
    case "table":
      window.insertTextAtCursor(
`| Colonne 1 | Colonne 2 |
|-----------|-----------|
| Valeur 1  | Valeur 2  |

`);
      break;
    case "toggle-lines":
      window.toggleLineNumbers && window.toggleLineNumbers();
      break;
    case "media-panel":
      window.openMediaPanel && window.openMediaPanel();
      break;
    case "emoji-panel":
      window.openEmojiPanel && window.openEmojiPanel();
      break;
    case "command-palette":
      window.openPalette && window.openPalette();
      break;
  }
});

