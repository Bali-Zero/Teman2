// GUILT b02 (item 1, PR3e, 2026-09-18, gate-10 obs 1, HIGH): a regex literal
// containing `//` used to be misread as a line comment, blanking the REST OF THE
// LINE -- the unpinned agent( call sharing this line must still be reported once the
// fix lands. Both are declared as ONE VariableDeclaration (comma-joined) so this is a
// single AST node and prettier-ignore preserves it verbatim on one physical line --
// two separate statements would always be pushed onto separate lines by prettier
// regardless of the ignore comment.
phase("Run");
// prettier-ignore
const ok = /https:\/\//.test(url), answer = await agent(`fetch it`, { label: `worker` });
