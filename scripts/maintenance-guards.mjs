import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";
import ts from "typescript";

const RESTRICTED_HOME_LINK = /\b(experiments?|prototypes?|inbox)\b/i;
const REQUIRED_PR_HEADING =
  /what changed,\s*which existing code,\s*what is still unknown/i;

export function findForbiddenNewFiles(files) {
  return files.filter((file) => {
    const name = path.basename(file);
    return (
      /^new_.+/i.test(name) ||
      /_v\d/i.test(name) ||
      /_new(?:\.|$)/i.test(name)
    );
  });
}

export function findHomeNavigationViolations({ hero, menu, footer }) {
  return [
    ["Home hero", hero],
    ["Top menu", menu],
    ["Footer", footer],
  ]
    .filter(([, source]) => RESTRICTED_HOME_LINK.test(source))
    .map(([area]) => `${area} links to or promotes an experiment, prototype, or inbox.`);
}

function isTestFile(file) {
  return (
    /(^|\/)tests?\//i.test(file) ||
    /(^|\/)test_[^/]+\.py$/i.test(file) ||
    /(^|\/)[^/]+_test\.py$/i.test(file) ||
    /(^|\/)[^/]+\.(test|spec)\.[cm]?[jt]sx?$/i.test(file)
  );
}

function countAssertions(file, content) {
  if (file.endsWith(".py")) {
    return content.split(/\r?\n/).reduce((count, line) => {
      if (/^\s*assert(?:\s|\()/.test(line)) return count + 1;
      return (
        count +
        (line.match(/\b(?:self\.)?assert[A-Z]\w*\s*\(/g)?.length ?? 0) +
        (line.match(/\bpytest\.raises\s*\(/g)?.length ?? 0)
      );
    }, 0);
  }

  const source = ts.createSourceFile(
    file,
    content,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.JS,
  );
  let count = 0;
  const visit = (node) => {
    if (ts.isCallExpression(node)) {
      const expression = node.expression;
      if (
        (ts.isIdentifier(expression) &&
          ["assert", "expect"].includes(expression.text)) ||
        (ts.isPropertyAccessExpression(expression) &&
          ts.isIdentifier(expression.expression) &&
          ["assert", "expect"].includes(expression.expression.text))
      ) {
        count += 1;
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return count;
}

function countTestAssertions(files) {
  return Object.entries(files)
    .filter(([file]) => isTestFile(file))
    .reduce((total, [file, content]) => total + countAssertions(file, content), 0);
}

export function compareTestIntegrity(
  baseFiles,
  headFiles,
  { tier2Approved = false } = {},
) {
  const baseTests = Object.keys(baseFiles).filter(isTestFile);
  const headTestSet = new Set(Object.keys(headFiles).filter(isTestFile));
  const deletedFiles = baseTests
    .filter((file) => !headTestSet.has(file))
    .sort();
  const baseAssertions = countTestAssertions(baseFiles);
  const headAssertions = countTestAssertions(headFiles);
  const violations = [];

  if (deletedFiles.length > 0) {
    violations.push(`Deleted test files: ${deletedFiles.join(", ")}.`);
  }
  if (headAssertions < baseAssertions) {
    violations.push(
      `Test assertions decreased from ${baseAssertions} to ${headAssertions}.`,
    );
  }

  return {
    ok: tier2Approved || violations.length === 0,
    deletedFiles,
    baseAssertions,
    headAssertions,
    violations: tier2Approved ? [] : violations,
  };
}

export function hasRequiredPrDescription(body) {
  return REQUIRED_PR_HEADING.test(body ?? "");
}

function git(args) {
  return execFileSync("git", args, { encoding: "utf8" }).trim();
}

function filesAtRef(ref, predicate) {
  const names = git(["ls-tree", "-r", "--name-only", ref])
    .split("\n")
    .filter(Boolean)
    .filter(predicate);
  return Object.fromEntries(
    names.map((file) => [file, git(["show", `${ref}:${file}`])]),
  );
}

function findSourceNode(source, fileName, predicate) {
  const syntax = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  let found;
  const visit = (node) => {
    if (!found && predicate(node)) found = node;
    if (!found) ts.forEachChild(node, visit);
  };
  visit(syntax);
  if (!found) throw new Error(`Could not locate ${fileName} source section.`);
  return source.slice(found.getStart(syntax), found.end);
}

export function homeNavigationSources() {
  const homePath = "src/routes/index.tsx";
  const home = readFileSync(homePath, "utf8");
  const hero = findSourceNode(
    home,
    homePath,
    (node) =>
      ts.isFunctionDeclaration(node) &&
      node.name?.text === "Hero",
  );
  const contentPath = "src/lib/content.ts";
  const content = readFileSync(contentPath, "utf8");
  const menu = findSourceNode(
    content,
    contentPath,
    (node) =>
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.name.text === "NAV",
  );
  return {
    hero,
    menu,
    footer: readFileSync("src/components/layout/site-footer.tsx", "utf8"),
  };
}

function approvedTier2(event) {
  return (event.pull_request?.labels ?? []).some(
    (label) => label.name === "tier-2-approved",
  );
}

function runPullRequestGuards() {
  const event = JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, "utf8"));
  const base = event.pull_request?.base?.sha;
  const head = git(["rev-parse", "HEAD"]);
  if (!base || !head) {
    throw new Error("Pull request base/head SHA is missing from the GitHub event.");
  }

  const addedFiles = git([
    "diff",
    "--diff-filter=A",
    "--name-only",
    `${base}...${head}`,
  ])
    .split("\n")
    .filter(Boolean);
  const forbiddenFiles = findForbiddenNewFiles(addedFiles);
  const testIntegrity = compareTestIntegrity(
    filesAtRef(base, isTestFile),
    filesAtRef(head, isTestFile),
    { tier2Approved: approvedTier2(event) },
  );
  const homeViolations = findHomeNavigationViolations(homeNavigationSources());
  const descriptionPresent = hasRequiredPrDescription(
    event.pull_request?.body,
  );

  console.log(
    `Test assertion count: ${testIntegrity.baseAssertions} -> ${testIntegrity.headAssertions}.`,
  );
  if (forbiddenFiles.length) {
    console.error(`Forbidden new filenames: ${forbiddenFiles.join(", ")}.`);
  }
  for (const violation of testIntegrity.violations) {
    console.error(violation);
  }
  for (const violation of homeViolations) console.error(violation);
  if (!descriptionPresent) {
    console.error(
      'PR description must include the heading "What changed, which existing code, what is still unknown".',
    );
  }

  if (
    forbiddenFiles.length ||
    !testIntegrity.ok ||
    homeViolations.length ||
    !descriptionPresent
  ) {
    process.exitCode = 1;
    return;
  }
  console.log("All repository maintenance guards passed.");
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  if (process.env.GITHUB_EVENT_NAME !== "pull_request") {
    console.log("Repository guards run on pull requests only.");
  } else {
    runPullRequestGuards();
  }
}
