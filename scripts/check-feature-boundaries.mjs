import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import ts from "typescript";

const root = path.resolve("apps/desktop/src");
const errors = [];
function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(file) : /\.tsx?$/.test(file) ? [file] : [];
  });
}
for (const file of walk(root)) {
  const relative = path.relative(root, file).split(path.sep).join("/");
  const owner = /^features\/([^/]+)\//.exec(relative)?.[1];
  if (relative.startsWith("components/") && !relative.startsWith("components/ui/")) {
    errors.push(`${relative}: feature UI belongs in features/<name>/components`);
  }
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
  );
  function inspect(node) {
    const specifier =
      ts.isImportDeclaration(node) || ts.isExportDeclaration(node)
        ? node.moduleSpecifier
        : ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword
          ? node.arguments[0]
          : undefined;
    if (specifier && ts.isStringLiteral(specifier)) {
      const value = specifier.text;
      const target = value.startsWith("@/")
        ? path.resolve(root, value.slice(2))
        : value.startsWith(".")
          ? path.resolve(path.dirname(file), value)
          : null;
      const destination = target && path.relative(root, target).split(path.sep).join("/");
      const feature = destination && /^features\/([^/]+)(?:\/(.*))?$/.exec(destination);
      if (feature && feature[1] !== owner) {
        const publicEntry = !feature[2] || /^index(?:\.ts)?$/.test(feature[2]);
        if (!publicEntry || (owner && !relative.startsWith(`features/${owner}/deps/`))) {
          errors.push(`${relative}: access ${value} through a public entry and a deps/ adapter`);
        }
      }
      if (relative.startsWith("shared/") && destination && /^(features|app)\//.test(destination)) {
        errors.push(`${relative}: shared code cannot depend on ${value}`);
      }
    }
    ts.forEachChild(node, inspect);
  }
  inspect(source);
}
if (errors.length) {
  console.error(errors.join("\n"));
  process.exitCode = 1;
} else {
  console.log("Feature boundaries passed.");
}
