import type { CssOperator } from "../index.ts";

function sites<T>(items: T[], pick: (count: number) => number): T | null {
  if (items.length === 0) return null;
  return items[pick(items.length)];
}

function decls(file: { rules: { declarations: { property: string; value: string; valueSpan: { start: number; end: number } }[] }[] }) {
  return file.rules.flatMap((rule) => rule.declarations);
}

export const deleteRule: CssOperator = {
  id: "delete-rule",
  archetype: "missing-style",
  language: "css",
  edit(file, ctx) {
    const rule = sites(file.rules, ctx.pick);
    if (!rule) return null;
    return { span: rule.span, replacement: "" };
  },
};

export const changeUnit: CssOperator = {
  id: "change-unit",
  archetype: "font-size",
  language: "css",
  edit(file, ctx) {
    const found = decls(file).filter((decl) => /^\d+(?:\.\d+)?px$/.test(decl.value));
    const decl = sites(found, ctx.pick);
    if (!decl) return null;
    const next = `${Number.parseFloat(decl.value) + 4}px`;
    return { span: decl.valueSpan, replacement: next };
  },
};

export const zIndex: CssOperator = {
  id: "z-index",
  archetype: "z-index",
  language: "css",
  edit(file, ctx) {
    const found = decls(file).filter((decl) => decl.property === "z-index" && /^-?\d+$/.test(decl.value));
    const decl = sites(found, ctx.pick);
    if (!decl) return null;
    return { span: decl.valueSpan, replacement: String(Number(decl.value) + 1) };
  },
};

export const overflow: CssOperator = {
  id: "overflow",
  archetype: "overflow",
  language: "css",
  edit(file, ctx) {
    const found = decls(file).filter((decl) => decl.property === "overflow" || decl.property.startsWith("overflow-"));
    const decl = sites(found, ctx.pick);
    if (!decl) return null;
    return { span: decl.valueSpan, replacement: decl.value === "hidden" ? "visible" : "hidden" };
  },
};

export const cssOperatorList = [deleteRule, changeUnit, zIndex, overflow];
