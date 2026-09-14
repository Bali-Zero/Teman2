/**
 * R19 "SIAP" primitives for the kita workspace — the shared module windows
 * K2-K5 import instead of re-inventing. See README.md for the token contract
 * and the API of each primitive.
 */
export * from "./tokens";
export { StatePill } from "./StatePill";
export { Masthead, Eyebrow } from "./Masthead";
export { DeskStrip } from "./DeskStrip";
export {
  HairlineGrid,
  HairlineHead,
  HairlineBody,
  HairlineRow,
  CellStack,
} from "./HairlineGrid";
export { NumberedList, Numeral, type NumberedItem } from "./NumberedList";
export { Stamp } from "./Stamp";
export { EmptyState } from "./EmptyState";
export { Slip } from "./Slip";
export { Notice } from "./Notice";
export { Field } from "./Field";
