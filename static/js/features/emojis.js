import { textarea } from "../core/main.js";

const panel = document.getElementById("emoji-panel");
if (panel) panel.style.display = "none";
// Assure que le panneau est bien fermé au chargement
//panel.style.display = "none";
const searchInput = document.getElementById("emoji-search");
const emojiList = document.getElementById("emoji-list");
const kaomojiList = document.getElementById("kaomoji-list");
const gifList = document.getElementById("gif-list");
const tabs = document.querySelectorAll("#emoji-tabs button");

const emojiData = [
  "😀","😁","😂","🤣","😅","😊","😍","😘","😎","🤓","🤔","🤯","😴","😡","👍","👎","🙏","🎉","🔥","⭐","✅","❌"
];
const kaomojiData = [
  "(＾▽＾)","(╯°□°）╯︵ ┻━┻","(づ｡◕‿‿◕｡)づ","(•̀ᴗ•́)و ̑̑","¯\\_(ツ)_/¯","(ノಠ益ಠ)ノ彡┻━┻"
];

let gifsData = []; // rempli par gifs.js

export function setGifs(gifs) {
  gifsData = gifs;
  renderGIFs("");
}

function insertAtCursor(text) {
  const pos = textarea.selectionStart;
  textarea.setRangeText(text, pos, pos, "end");
  window.updatePreview && window.updatePreview();
}

function renderEmojis(filter) {
  emojiList.innerHTML = "";
  emojiData
    .filter(e => !filter || e.includes(filter))
    .forEach(e => {
      const div = document.createElement("div");
      div.className = "emoji-item";
      div.textContent = e;
      div.onclick = () => insertAtCursor(e);
      emojiList.appendChild(div);
    });
}

function renderKaomojis(filter) {
  kaomojiList.innerHTML = "";
  kaomojiData
    .filter(k => !filter || k.toLowerCase().includes(filter.toLowerCase()))
    .forEach(k => {
      const div = document.createElement("div");
      div.className = "kaomoji-item";
      div.textContent = k;
      div.onclick = () => insertAtCursor(k);
      kaomojiList.appendChild(div);
    });
}

function renderGIFs(filter) {
  gifList.innerHTML = "";
  gifsData
    .filter(url => !filter || url.toLowerCase().includes(filter.toLowerCase()))
    .forEach(url => {
      const div = document.createElement("div");
      div.className = "gif-item";
      div.innerHTML = `<img src="${url}">`;
      div.onclick = () => insertAtCursor(`![gif](${url})`);
      gifList.appendChild(div);
    });
}

searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim();
  if (emojiList.style.display !== "none") {
    renderEmojis(q);
  } else if (kaomojiList.style.display !== "none") {
    renderKaomojis(q);
  } else {
    renderGIFs(q);
  }
});

tabs.forEach(btn => {
  btn.addEventListener("click", () => {
    tabs.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    emojiList.style.display = tab === "emoji" ? "flex" : "none";
    kaomojiList.style.display = tab === "kaomoji" ? "flex" : "none";
    gifList.style.display = tab === "gif" ? "flex" : "none";
  });
});

document.getElementById("emoji-close").onclick = () => panel.style.display = "none";

window.openEmojiPanel = function() {
  panel.style.display = "flex";
  tabs[0].click();
  renderEmojis("");
  renderKaomojis("");
  renderGIFs(""); // si déjà récupérés
};

