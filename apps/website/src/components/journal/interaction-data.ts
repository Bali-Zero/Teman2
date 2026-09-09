import type { Data } from "./article-model";
const record = (v: Data | undefined): v is Record<string, Data> => !!v && typeof v === "object" && !Array.isArray(v);
export const label = (v: Data | undefined): string => typeof v === "string" ? v.slice(0, 4000) : "";
export interface CheckItem { id: string; text: string; detail: string; group: string; required: boolean }
export function checklistData(props: Record<string, Data>): CheckItem[] | null {
  if (!Array.isArray(props.items) || !props.items.length || props.items.length > 100) return null;
  const items = props.items.map((v, i): CheckItem | null => {
    if (typeof v === "string" && v.trim()) return { id: String(i), text: v, detail: "", group: "", required: false };
    if (!record(v) || !(label(v.label) || label(v.text)).trim()) return null;
    return { id: label(v.id) || String(i), text: label(v.label) || label(v.text),
      detail: [label(v.description), ...(Array.isArray(v.subItems) ? v.subItems.map(label) : [])].filter(Boolean).join(" "),
      group: [...new Set([label(v.group), label(v.category)].filter(Boolean))].join(" / "), required: v.required === true };
  });
  if (items.some((v) => !v)) return null;
  const valid = items as CheckItem[];
  return new Set(valid.map((v) => v.id)).size === valid.length ? valid : null;
}
export interface DecisionOption { text: string; detail: string; next: string }
export interface DecisionNode { id: string; question: string; detail: string; options: DecisionOption[]; result?: { title: string; description: string; recommendations: string[]; nextSteps: string[] } }
export interface DecisionData { start: string; nodes: DecisionNode[] }
export function decisionData(props: Record<string, Data>): DecisionData | null {
  if (!Array.isArray(props.nodes) || !props.nodes.length || props.nodes.length > 100) return null;
  const nodes: DecisionNode[] = [];
  for (const value of props.nodes) {
    if (!record(value) || !label(value.id).trim()) return null;
    const node: DecisionNode = { id: label(value.id), question: label(value.question), detail: label(value.description), options: [] };
    if (value.isResult === true || record(value.result)) {
      if (!record(value.result) || !label(value.result.title) || !label(value.result.description)) return null;
      const strings = (v: Data | undefined): string[] => Array.isArray(v) ? v.map(label).filter(Boolean) : [];
      node.result = { title: label(value.result.title), description: label(value.result.description), recommendations: strings(value.result.recommendations), nextSteps: strings(value.result.nextSteps) };
    } else {
      if (!node.question || !Array.isArray(value.options) || !value.options.length || value.options.length > 20) return null;
      for (const option of value.options) {
        if (!record(option) || !label(option.label) || !(label(option.nextNodeId) || label(option.next))) return null;
        node.options.push({ text: label(option.label), detail: label(option.description), next: label(option.nextNodeId) || label(option.next) });
      }
    }
    nodes.push(node);
  }
  const byId = new Map(nodes.map((v) => [v.id, v]));
  const start = label(props.startNodeId) || (byId.has("start") ? "start" : nodes[0].id);
  if (byId.size !== nodes.length || !byId.has(start)) return null;
  const done = new Set<string>(), active = new Set<string>();
  function reachesResult(id: string): boolean {
    if (active.has(id) || !byId.has(id)) return false;
    if (done.has(id)) return true;
    active.add(id);
    for (const option of byId.get(id)!.options) if (!reachesResult(option.next)) return false;
    active.delete(id); done.add(id); return true;
  }
  return nodes.every((node) => reachesResult(node.id)) ? { start, nodes } : null;
}
