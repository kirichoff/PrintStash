import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function sourceFiles(root: string): string[] {
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(root, entry.name);
    return entry.isDirectory() ? sourceFiles(full) : /\.(ts|tsx)$/.test(entry.name) ? [full] : [];
  });
}

describe("dialog design rules", () => {
  it("never uses browser-native prompt, alert, or confirm dialogs", () => {
    const root = path.resolve(__dirname, "../..");
    const findings = sourceFiles(root).flatMap((file) => {
      const source = fs.readFileSync(file, "utf8");
      return /window\.(prompt|alert|confirm)\s*\(/.test(source) ? [path.relative(root, file)] : [];
    });
    expect(findings).toEqual([]);
  });
});
