import MarkdownIt from "markdown-it";
import texmath from "markdown-it-texmath";
import katex from "katex";

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
}).use(texmath, {
  engine: katex,
  delimiters: "dollars",
  katexOptions: { throwOnError: false }
});

export function renderMarkdown(content) {
  return markdown.render(content || "");
}
