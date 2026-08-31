#!/usr/bin/env node
// Renders every marked Mermaid diagram in docs/**/*.md to docs/assets/<name>.svg
// and embeds the SVG image below the fenced block. Idempotent.
// Requires @mermaid-js/mermaid-cli (mmdc) on PATH; falls back to `npx -y`.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const docsDir = path.join(root, "docs");
const assetsDir = path.join(docsDir, "assets");
const MARKER = /<!-- diagram: ([a-z0-9-]+) -->\r?\n```mermaid\r?\n([\s\S]*?)```/g;

function findMmdc() {
  try {
    execFileSync("mmdc", ["--version"], { stdio: "ignore" });
    return "mmdc";
  } catch {
    return "npx";
  }
}

function markdownFiles(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter((e) => e.isFile() && e.name.endsWith(".md"))
    .map((e) => path.join(e.parentPath ?? e.path, e.name))
    .sort();
}

function render(name, source, mmdc, tmp, puppeteerCfg) {
  const mmd = path.join(tmp, `${name}.mmd`);
  fs.writeFileSync(mmd, source);
  const args = ["-i", mmd, "-o", path.join(assetsDir, `${name}.svg`), "-b", "white", "-p", puppeteerCfg];
  execFileSync(mmdc, mmdc === "npx" ? ["-y", "@mermaid-js/mermaid-cli", ...args] : args, {
    stdio: "inherit",
  });
}

function processFile(file, mmdc, tmp, puppeteerCfg) {
  let text = fs.readFileSync(file, "utf8");
  const matches = [...text.matchAll(MARKER)];
  if (matches.length === 0) return 0;
  const rel = path.relative(path.dirname(file), docsDir);
  const relPrefix = rel || ".";
  // back-to-front so earlier match indices stay valid as we splice
  for (const match of matches.reverse()) {
    const name = match[1];
    render(name, match[2], mmdc, tmp, puppeteerCfg);
    const embed = `![${name} diagram](${relPrefix}/assets/${name}.svg)`;
    const blockEnd = match.index + match[0].length;
    const rest = text.slice(blockEnd);
    const embedRe = new RegExp(`\\r?\\n\\r?\\n!\\[[^\\]]*\\]\\([^)]*assets/${name}\\.svg\\)`);
    const newRest = embedRe.test(rest) ? rest.replace(embedRe, `\n\n${embed}`) : `\n\n${embed}${rest}`;
    text = text.slice(0, blockEnd) + newRest;
    console.log(`rendered ${name} (${path.relative(root, file)})`);
  }
  fs.writeFileSync(file, text);
  return matches.length;
}

function main() {
  const files = markdownFiles(docsDir);
  const seen = new Map();
  for (const file of files) {
    for (const match of fs.readFileSync(file, "utf8").matchAll(MARKER)) {
      if (seen.has(match[1])) throw new Error(`duplicate diagram name: ${match[1]}`);
      seen.set(match[1], file);
    }
  }
  if (seen.size === 0) {
    console.log("no marked diagrams found");
    return;
  }

  fs.mkdirSync(assetsDir, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "diagrams-"));
  const puppeteerCfg = path.join(tmp, "puppeteer.json");
  fs.writeFileSync(puppeteerCfg, JSON.stringify({ args: ["--no-sandbox"] }));
  const mmdc = findMmdc();

  let total = 0;
  for (const file of files) total += processFile(file, mmdc, tmp, puppeteerCfg);
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`done: ${total} diagram(s) -> ${path.relative(root, assetsDir)}`);
}

main();
