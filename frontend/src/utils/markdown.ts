/**
 * Markdown 渲染工具。
 * 使用 markdown-it + highlight.js 实现代码高亮。
 */

import MarkdownIt from "markdown-it";
import hljs from "highlight.js";

const md = new MarkdownIt({
  html: false,          // 安全：禁用原始 HTML
  linkify: true,        // 自动链接
  breaks: true,         // 换行转 <br>
  highlight(str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`;
      } catch { /* fall through */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`;
  },
});

/**
 * 渲染 Markdown 为 HTML，附带安全的 XSS 过滤。
 */
export function renderMarkdown(text: string): string {
  if (!text) return "";
  // 移除潜在的脚本标签（额外安全层）
  const sanitized = text.replace(/<script[\s\S]*?<\/script>/gi, "");
  return md.render(sanitized);
}

/**
 * 截取纯文本（去掉 Markdown 标记）。
 */
export function stripMarkdown(text: string, maxLen = 100): string {
  const plain = text
    .replace(/[#*`>\[\]()!_~]/g, "")
    .replace(/\n+/g, " ")
    .trim();
  return plain.length > maxLen ? plain.slice(0, maxLen) + "…" : plain;
}
