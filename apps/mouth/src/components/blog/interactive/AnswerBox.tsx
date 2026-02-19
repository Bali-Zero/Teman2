/**
 * AnswerBox and KeyTakeaway - MDX-embeddable answer-first components
 *
 * Re-exports from seo/AnswerBox for use in MDX articles.
 * Place <AnswerBox> immediately after H1 for AI citation optimization.
 *
 * Usage in MDX:
 * <AnswerBox>
 *   PT PMA is Indonesia's foreign-owned company structure, costing from IDR 20M.
 * </AnswerBox>
 *
 * <KeyTakeaway points={["KITAS required for work", "PT PMA = 100% foreign ownership"]} />
 */
export { AnswerBox, KeyTakeaway } from "@/components/seo/AnswerBox";
