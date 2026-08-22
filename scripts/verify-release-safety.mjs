import { readFile, readdir } from "node:fs/promises";
import { join, relative } from "node:path";

const root = process.cwd();
const skipped = new Set(["node_modules", ".git", ".expo", "reference-fastapi-platform"]);
const allowedPlaceholders = new Set(["REPLACE_WITH_STRIPE_SECRET_KEY", "REPLACE_WITH_STRIPE_WEBHOOK_SECRET", "REPLACE_WITH_RESEND_API_KEY"]);
const findings = [];

async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (skipped.has(entry.name)) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await walk(path);
    if (!entry.isFile() || /\.(png|jpg|jpeg|webp|woff2|lock)$/i.test(entry.name)) continue;
    const content = await readFile(path, "utf8").catch(() => null);
    if (!content) continue;
    const file = relative(root, path);
    for (const match of content.matchAll(/(?:^|[^A-Za-z0-9])((?:sk|rk)_(?:live|test)_[A-Za-z0-9_]{12,}|whsec_[A-Za-z0-9_]{12,}|re_[A-Za-z0-9_]{12,})/gm)) {
      const token = match[1];
      if (!allowedPlaceholders.has(token)) findings.push(`${file}: potential credential pattern ${token.slice(0, 10)}…`);
    }
    if (/(?:R2_SECRET_ACCESS_KEY|STRIPE_SECRET_KEY|RESEND_API_KEY)\s*=\s*[^R\n][^\n]*/.test(content) && !file.endsWith(".example")) {
      findings.push(`${file}: server-only secret assignment outside an example file`);
    }
  }
}

await walk(root);
if (findings.length) {
  console.error("Release safety check failed:\n" + findings.join("\n"));
  process.exit(1);
}
console.log("Release safety check passed: no likely live payment, email, or R2 credentials in tracked source.");
