import type { Edit, JsxOperator, ParsedSource } from "../index.ts";

function sites<T>(items: T[], pick: (count: number) => number): T | null {
  if (items.length === 0) return null;
  return items[pick(items.length)];
}

export const removeClass: JsxOperator = {
  id: "remove-class",
  archetype: "missing-style",
  language: "jsx",
  edit(file, ctx) {
    const tokens = file.elements.flatMap((el) => {
      const all = el.className?.tokens ?? [];
      return all.filter((token) => token.text === "flex-row" || token.text === "flex-col" || all.length > 1);
    });
    const token = sites(tokens, ctx.pick);
    if (!token) return null;
    return { span: token.span, replacement: "" };
  },
};

export const swapFlexDirection: JsxOperator = {
  id: "swap-flex-direction",
  archetype: "flex-direction",
  language: "jsx",
  edit(file, ctx) {
    const tokens = file.elements.flatMap((el) =>
      (el.className?.tokens ?? []).filter((token) => token.text === "flex-row" || token.text === "flex-col"),
    );
    const token = sites(tokens, ctx.pick);
    if (!token) return null;
    return { span: token.span, replacement: token.text === "flex-row" ? "flex-col" : "flex-row" };
  },
};

export const dropProp: JsxOperator = {
  id: "drop-prop",
  archetype: "wrong-element",
  language: "jsx",
  edit(file, ctx) {
    const props = file.elements.flatMap((el) => el.props);
    const prop = sites(props, ctx.pick);
    if (!prop) return null;
    return { span: prop.span, replacement: "" };
  },
};

export const changeElement: JsxOperator = {
  id: "change-element",
  archetype: "wrong-element",
  language: "jsx",
  edit(file, ctx) {
    const el = sites(file.elements, ctx.pick);
    if (!el || el.name.length === 0) return null;
    const next = el.name === "div" ? "span" : "div";
    if (!el.closeNameSpan) return { span: el.nameSpan, replacement: next };
    const mid = file.text.slice(el.nameSpan.end, el.closeNameSpan.start);
    const edit: Edit = {
      span: { start: el.nameSpan.start, end: el.closeNameSpan.end },
      replacement: next + mid + next,
    };
    return edit;
  },
};

export const jsxOperatorList = [removeClass, swapFlexDirection, dropProp, changeElement];

export function changedSource(file: ParsedSource, edit: Edit): string {
  return file.text.slice(0, edit.span.start) + edit.replacement + file.text.slice(edit.span.end);
}
