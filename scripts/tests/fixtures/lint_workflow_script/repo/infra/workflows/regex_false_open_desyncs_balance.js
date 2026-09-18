// SAFETY NET fixture (item 1, PR3e, 2026-09-18): `}` is a listed regex-opener
// character (the mandate's own prefix-token rule), and a `}` that closes an OBJECT
// LITERAL (not a block) can genuinely be followed by DIVISION in valid JS -- `x = {a:
// 1} / 2` is unambiguous real JS, since `{a: 1}` cannot be a statement-opening block
// here (it is the right-hand side of `=`). The `/` right after `}` below is wrongly
// read as a regex open; it swallows the `open(` call's own `(` into a phantom span
// while its matching `)` falls outside -- this must not report CLEAN, it must refuse
// with exit 2 (cicatrix #2: never report CLEAN on text you could not read).
phase("Run");
// prettier-ignore
const ratio = { n: 1 } / open(mismatched / close) + 1;
