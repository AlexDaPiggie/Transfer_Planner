export function startTypingHeadline(headline) {
  const textNode = headline?.querySelector(".typing-text");
  if (!headline || !textNode) return;

  const text = headline.dataset.text || headline.getAttribute("aria-label") || "";
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    textNode.textContent = text;
    return;
  }

  let index = 0;
  let deleting = false;
  function tick() {
    textNode.textContent = text.slice(0, index);
    if (!deleting && index < text.length) {
      index += 1;
      window.setTimeout(tick, 72);
    } else if (!deleting) {
      deleting = true;
      window.setTimeout(tick, 4000);
    } else if (index > 0) {
      index -= 1;
      window.setTimeout(tick, 42);
    } else {
      deleting = false;
      window.setTimeout(tick, 520);
    }
  }
  tick();
}

export function typingHeadlineMarkup(text) {
  const safeText = text.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  return `<h1 class="typing-headline" aria-label="${safeText}" data-text="${safeText}"><span class="typing-text" aria-hidden="true"></span><span class="typing-cursor" aria-hidden="true"></span></h1>`;
}
