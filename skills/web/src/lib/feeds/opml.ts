/** OPML 订阅列表. 无 xmlUrl 的 outline 当作文件夹, 路径写入 group. */

export type OpmlOutline = {
  name: string;
  url: string;
  group: string;
};

export class OpmlParseError extends Error {
  constructor() {
    super("invalid_opml");
    this.name = "OpmlParseError";
  }
}

function attrCi(el: Element, name: string): string | null {
  const lower = name.toLowerCase();
  for (const item of el.attributes) {
    if (item.name.toLowerCase() === lower) {
      const value = item.value.trim();
      return value === "" ? null : value;
    }
  }
  return null;
}

function isHttpUrl(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

function outlineName(el: Element, url: string): string {
  const name = attrCi(el, "text") ?? attrCi(el, "title");
  if (name !== null) {
    return name;
  }
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function isXmlParseError(doc: Document): boolean {
  if (doc.getElementsByTagName("parsererror").length > 0) {
    return true;
  }
  const root = doc.documentElement;
  return root === null || root.localName === "parsererror";
}

function folderGroup(el: Element): string {
  const parts: string[] = [];
  let parent = el.parentElement;
  while (parent != null && parent.localName.toLowerCase() === "outline") {
    if (attrCi(parent, "xmlUrl") == null) {
      const name = attrCi(parent, "text") ?? attrCi(parent, "title");
      if (name != null) {
        parts.unshift(name.replaceAll("/", "-"));
      }
    }
    parent = parent.parentElement;
  }
  return parts.join("/");
}

/** 从 OPML XML 抽出订阅. 非法 XML 抛 OpmlParseError; 无 xmlUrl 返回空数组. */
export function parseOpml(xml: string): OpmlOutline[] {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  if (isXmlParseError(doc)) {
    throw new OpmlParseError();
  }
  const seen = new Set<string>();
  const result: OpmlOutline[] = [];
  for (const outline of doc.getElementsByTagName("outline")) {
    const url = attrCi(outline, "xmlUrl");
    if (url === null || !isHttpUrl(url) || seen.has(url)) {
      continue;
    }
    seen.add(url);
    result.push({ name: outlineName(outline, url), url, group: folderGroup(outline) });
  }
  return result;
}
