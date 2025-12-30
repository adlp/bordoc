import { setGifs } from "./emojis.js";

async function loadGIFs() {
  const res = await fetch("/gifteurs");
  if (!res.ok) return;
  const data = await res.json();
  const gifs = data.gifs || [];
  setGifs(gifs);
}

loadGIFs();

