import { filenameInput } from "../core/main.js";

const backlinksList = document.getElementById("backlinks-list");

window.updateBacklinks = async function() {
  const filename = filenameInput.value.trim();
  if (!filename) {
    backlinksList.innerHTML = "<li>Aucun fichier actif</li>";
    return;
  }
  const res = await fetch("/backlinks?file=" + encodeURIComponent(filename));
  if (!res.ok) {
    backlinksList.innerHTML = "<li>Erreur backlinks</li>";
    return;
  }
  const data = await res.json();
  backlinksList.innerHTML = "";
  if (!data.files || data.files.length === 0) {
    backlinksList.innerHTML = "<li>Aucun backlink</li>";
    return;
  }
  data.files.forEach(f => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.textContent = f;
    a.onclick = (e) => {
      e.preventDefault();
      window.openTab && window.openTab(f, "");
      // le contenu sera chargé par /read quand tu veux
    };
    li.appendChild(a);
    backlinksList.appendChild(li);
  });
};

