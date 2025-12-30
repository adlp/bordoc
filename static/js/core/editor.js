import { textarea, lastSavedContent } from "./main.js";

window.wrap = function(before, after) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selected = textarea.value.substring(start, end);
  textarea.setRangeText(before + selected + after, start, end, "end");
  window.updatePreview && window.updatePreview();
};

window.insertTextAtCursor = function(text) {
  const pos = textarea.selectionStart;
  textarea.setRangeText(text, pos, pos, "end");
  window.updatePreview && window.updatePreview();
};

