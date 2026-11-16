// answerBlocks.js — splits answer text into paragraphs and bullet lists, with each [n] pulled out
// as a citation. data in, data out, so the components only have to render

const CITATION = /\[(\d+)\]/g;
const BULLET = /^[-*•]\s+(.*)$/;

export function toBlocks(text) {
  const blocks = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const bullet = trimmed.match(BULLET);
    if (!bullet) {
      blocks.push({ type: "paragraph", parts: toParts(trimmed) });
      continue;
    }
    const previous = blocks.at(-1);
    if (previous?.type === "list") previous.items.push(toParts(bullet[1]));
    else blocks.push({ type: "list", items: [toParts(bullet[1])] });
  }
  return blocks;
}

export function toParts(text) {
  const parts = [];
  let last = 0;
  for (const match of text.matchAll(CITATION)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index) });
    parts.push({ cite: Number(match[1]) });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}
