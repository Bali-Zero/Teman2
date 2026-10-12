# KBLI Navigator census: the mark-order scan (spec)

Status: SPEC, not implemented. Written 2026-10-12 from the #8309 and #8327 gate verdicts and the lead's re-ruling. The code that exists
(`apps/kbli-navigator-macos/Tools/design/mark_order_check.py`) is a first-pass lint, declared as such in its docstring; this document is
what replaces it, in its own lane, and the guilt set below is what its tests must hold.

## 1. What the scan protects

A `.censusFrame(name)` mark reports the element's LAYOUT frame, where it is meant to land; `png_census.py` verifies that the ink is there.
That check can only fail when frame and ink disagree. Two things make them agree by construction, and the census is then blind:

- a mark placed BEFORE an animation modifier travels with the move;
- a MOVE applied to the marked element, or to a container that holds it, after the mark moves the frame and the ink together.

So the order of a mark in its modifier chain, and what the enclosing chains do to it, cannot be seen from pixels. It has to be read from
the source. Rule (lead 2026-10-12): the mark goes after every animation; no MOVE applies to a marked element or to anything that holds it;
a static nudge is layout (`padding`, alignment), never `.offset`.

## 2. Why not a hand-written parser

The current scan is a hand-written reader of Swift chains. Two successive cures (#8309, #8327) each closed the shapes the previous gate
named and each left a new set open: a Swift expression chain with trailing closures, labelled closures, `#if` blocks, ViewModifier bodies
and extension conformances is an unbounded surface for a regex-and-brace reader. Builder Contract 1 stops a fix-of-a-fix at depth 1; the
surface is under-specified, so this document is the spec. **Recommended implementation: SwiftSyntax**, as a small tool target (a Swift
package executable, buildable on Pro with the toolchain already there), reading `Sources/**/*.swift` into a syntax tree and answering the
questions below on the tree, not on text. The text lint stays only until that tool lands.

## 3. The questions the tool answers

**Chain grammar** (after strings and comments are out of the tree, which SwiftSyntax does by construction). A link is `.name`, then an
optional `( ... )`, then an optional trailing closure `{ ... }` that may begin on the NEXT line, then any number of labelled closures
`label: { ... }`. A postfix `#if cond ... (#elseif cond ...)* (#else ...)? #endif` is part of the chain; every branch's links count,
because either may compile. Walk forwards from the mark and backwards to the root over this grammar.

**Fail closed.** If either walk stops on a token the grammar does not know, that is a finding ("unreadable chain"), never a silent stop.

**Walk out of closures.** A mark inside a group (a closure or an argument) of an enclosing expression takes that expression's links as its
own:
- if the group belongs to a link L (`.overlay { ... }`, `.background(...)`), only the links AFTER L apply (an offset BEFORE the overlay
  does not move the mark: innocent I2);
- if the group belongs to the root (`Group`, `VStack`, `ForEach`, ...), every link applies;
- `if` / `else` / `switch` blocks are transparent;
- stop at a declaration body (`var x: some View {`, `func ... {`, `var body`).

Then either resolve marked members and types at their use sites by name (`matrix.offset(y: 4)`, L5 / B15), exempting the snapshot
harness's camera (`Snapshot.swift`, the footer band's pan, not in `render_set`) as the innocence case, or keep that limit declared and
bounded.

**MOVE** is `.offset(` plus every function or ViewModifier struct whose body applies a MOVE, closed to a fixed point (that catches the
real `HoverLift`, `Immersion.swift`, `.offset(y: over ? -3 : 0)`). The built-in render-only effects `scaleEffect`, `rotationEffect`,
`rotation3DEffect`, `transformEffect`, `projectionEffect` and `matchedGeometryEffect` move the ink without moving the layout, so they ARE
moves in this rule; a spec decision per effect may rule one out explicitly, in writing.

**ANIMATION** is `.transition` plus every Animatable / AnimatableModifier / GeometryEffect type, its conformance read from the type head
OR from an `extension T: ...` (L7), plus every function or ViewModifier struct that applies one (L8), closed to a fixed point.

## 4. Bindings from the gates

- `.position(` and `.alignmentGuide(` are LAYOUT, not moves: the mark reads where the element lands and the ink is there. They stay
  allowed. (Map pins of the panel head are placed this way, never with `.offset` on a marked pin.)
- `scaleEffect` / `rotationEffect` are moves; they are not read by the lint today and none is live on a marked element.
- A mark inside an `.overlay { ... }` of another element has no MOVE or ANIMATION link after that overlay on the host chain (the L4 / B5
  shape; the panel head's glyph beside the title is exactly it).

## 5. Limits of the lint that exists (the guilt set to implement)

Each is a guilt the tool must fail, with the gate's case id. None is live in `Sources/` today (22 move/animation sites, none with a
marked element in its subject; 0 postfix `#if`; the 26 labelled trailing closures are all on roots).

| id | shape | cases |
|---|---|---|
| L1 | trailing closure with the `{` on the next line, with parens or without | B1a, B1b |
| L2 | labelled trailing closures `label: { ... }`, forwards and backwards | B2a, B2b |
| L3 | postfix `#if` / `#elseif` / `#else` / `#endif` inside the chain | B3a, B3b, B3c |
| L4 | a mark inside a closure or argument whose enclosing chain then moves or animates: `Group { mark }.offset`, `host.overlay { mark }.offset` / `.modifier(Beat)`, `ForEach { mark }.offset` | B4, B5a, B5b, B5c |
| L5 | a marked view used by name and moved where it is used, e.g. `matrix.offset(...)`; offsets as well as animations | B15 |
| L6 | a MOVE helper: a func or ViewModifier whose body applies `.offset`, the real `HoverLift` included | B6, B7a, B7b |
| L7 | an Animatable conformance declared in an `extension` | B8 |
| L8 | a non-Animatable ViewModifier that applies Beat or another animation | B11 |
| L9 | built-in render effects: scaleEffect, rotationEffect, rotation3DEffect, transformEffect, projectionEffect, matchedGeometryEffect | B14 |

Measured at the #8327 gate: `Group { chip.national }.offset(y: 4)` moves `chip.national`'s frame from y 71 to y 75 together with its ink and
`png_census` passes it (C23: "3 chips, off their state's tone: none"); the same on the ladder's overlay host is caught only by C21, which
relates the ladder to the matrix rule. Only a check that relates the element to ANOTHER element can see it.

## 6. Guilt and innocence set

**Guilt (each must fail):** G1-G9 of #8309 (a mark before its Beat; a mark then `.offset`; an `.offset` above the mark; a mark then
`DrawnRule`; a mark, a multi-line `.overlay { }`, then `.offset`; an `.offset`, a multi-line `.background { }`, then the mark; a mark then a
wrapped `.modifier(` / `Beat(...))`; a mark then a helper that applies Beat; `.offset (y:)` with a space), the ternary forms
(`.offset(y: c ? 0 : 3)`, `.modifier(c ? Beat(...) : Beat(...))`), plus B1a, B1b, B2a, B2b, B3a, B3b, B3c, B4, B5a, B5b, B5c, B6, B7a, B7b,
B8, B11 and B14, and B15 when use sites are resolved.

**Innocence (each must pass):** I1-I7 (an `.offset` or `Beat` inside a string, a comment, a nested block comment, a raw string, a
multi-line string, or inside an EARLIER `.background { }` closure that moves the background only); a ternary that is not a move
(`.opacity(c ? 1 : 0.5)`); an `.offset` on the host BEFORE its `.overlay { mark }` (I2); `.position` and `.alignmentGuide`; the snapshot
camera pan; and every real chain in `Sources/` (21 marks at the time of writing).

## 7. Order of work

1. This spec lands with the lint's declared limits (docstrings in `mark_order_check.py` and `CensusFrame.swift`).
2. The panel-head PRs add no mark with a chain the lint cannot read whole, and no mark inside an `.overlay { }` that a later link moves
   (the B5 shape), until the tool lands. C24's self-test also gains the "marked but not in the record" case on its own.
3. The SwiftSyntax tool is its own PR (own lane, own gate), before `HoverLift` lands on a marked element or a container of one (2c').
