import SwiftUI

/// D4 "Anima Indonesiana" (2026-08-11) — procedural decorative motifs, SwiftUI `Canvas` only (no
/// new PNG assets per spec). Every view here is decorative-only: `.allowsHitTesting(false)` +
/// `.accessibilityHidden(true)` unconditionally, ZERO animation, and gated on
/// `Theme.decorationsVisible` (hides entirely under Increase Contrast — decorations must never
/// compete with legibility). Colors/alphas route through the `Theme.decor*` tokens.
///
/// GUARDRAILS (from the D4 research, binding on every motif in this file): never Garuda
/// Pancasila (protected national emblem, UU 24/2009) — `PadiKapasSprigs` draws ONLY the two loose
/// botanical sprigs, never the shield+eagle composition they normally sit inside; never batik
/// parang; the archipelago geography (`ArchipelagoConstellation`) stays end-to-end complete,
/// Sumatra through Papua/Maluku — never a cropped western-only silhouette; no imitation of
/// banknote security marks.
///
/// PROVENANCE (2026-08-11, v2): every formula below is a direct, verbatim port of the Zero-
/// approved reference draft's JS canvas functions (`kbli-d4-draft.html` §script — `rosette()`,
/// `guilloche()`, `goldenArc()`, `sprigs()`, `coastDots()`/`ISLANDS`/`proj()`, and the `'broken'`
/// squiggle case), not a re-derivation from the spec's PROSE description. An earlier v1 pass,
/// built while the draft was unreachable, approximated these from prose alone (functionally
/// plausible but NOT what Zero actually saw) — this file replaces that pass wholesale rather than
/// patching it, since nearly every constant differs (rosette layer amplitudes/base-radius/missing
/// inner ring, golden-arc geometry family, sprig grain/boll placement, squiggle dashing, and the
/// sidebar band's underlying motif — `guilloche()`, a wavy multi-row band, NOT `rosette()`).

// MARK: - Guilloché rosette (ChatView medallion + ChatPlaceholderColumn)

/// A 3-layer polar "rose": `r(θ) = R·(0.72 + f·sin(k·θ))` per layer, for (k,f) in
/// `[(12,.16),(18,.10),(7,.22)]` — draft's `rosette()` — plus one small inner circle at `R·0.34`.
/// All layers + the inner circle share ONE alpha (the draft never grades alpha across layers —
/// depth reads from the differing frequencies, not opacity tiers) and the shared `decorLineWidth`
/// stroke width.
struct GuillocheRosette: View {
    var tint: Color = Theme.decor
    var size: CGFloat = 120
    /// Draft: `rosette(x,cx,cy,R,col,alpha)` — the medallion role (ChatView) passes `p.amb`
    /// (ambient, sits as a watermark behind readable chip text); a standalone rosette
    /// (ChatPlaceholderColumn) defaults to `p.focal` (a touch more present with nothing behind it).
    var alpha: Double = Theme.decorFocalAlpha

    private static let layers: [(k: Double, f: Double)] = [(12, 0.16), (18, 0.10), (7, 0.22)]

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                Canvas { context, canvasSize in
                    let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
                    let R = min(canvasSize.width, canvasSize.height) / 2
                    let style = StrokeStyle(lineWidth: Theme.decorLineWidth)
                    let strokeColor = GraphicsContext.Shading.color(tint.opacity(alpha))

                    for (k, f) in Self.layers {
                        var path = Path()
                        let steps = 320
                        for step in 0...steps {
                            let a = (Double(step) / Double(steps)) * 2 * .pi
                            let r = R * (0.72 + f * sin(k * a))
                            let pt = CGPoint(x: center.x + CGFloat(cos(a)) * r, y: center.y + CGFloat(sin(a)) * r)
                            if step == 0 { path.move(to: pt) } else { path.addLine(to: pt) }
                        }
                        path.closeSubpath()
                        context.stroke(path, with: strokeColor, style: style)
                    }
                    // Draft: `x.beginPath(); x.arc(0,0,R*.34,0,7); x.stroke();` — one inner ring.
                    let innerR = R * 0.34
                    let innerRect = CGRect(x: center.x - innerR, y: center.y - innerR, width: innerR * 2, height: innerR * 2)
                    context.stroke(Path(ellipseIn: innerRect), with: strokeColor, style: style)
                }
                .frame(width: size, height: size)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: - Guilloché band (sidebar footer band + About window background wash)

/// The engraved multi-row wavy-line motif — draft's `guilloche(x,w,h,col,alpha,rows,amp,band)`.
/// Deliberately a DIFFERENT function from `rosette()` above (an earlier v1 pass used a small
/// rosette for the sidebar band — wrong motif family; the draft's `'band'`/`'about'` canvas roles
/// both call `guilloche()`, never `rosette()`). Each of `rows` lines follows
/// `y = y0 + rowOffset + amp·sin(px/34 + k·1.9) + amp·0.55·sin(px/12.6 + k·3.7)`.
struct GuillocheBand: View {
    /// `nil` lets the Canvas expand to fill whatever width its container proposes — the sidebar
    /// footer band's own width varies with the split view. The About window wash passes an
    /// explicit width to share the exact canvas region as its sibling decorations there.
    var width: CGFloat?
    var height: CGFloat = 64
    var tint: Color = Theme.decor
    var alpha: Double = Theme.decorAmbientAlpha
    var rows: Int = 4
    var amplitude: Double = 5
    /// (verticalCenterFraction, spanPoints) — draft's `band=[y0, span]`. `nil` centers every row on
    /// the vertical midline with zero spread (draft's `band==null` fallback; unused by either D4
    /// call site, kept only for API parity with the source function).
    var band: (centerFraction: CGFloat, span: CGFloat)?

    init(width: CGFloat? = nil, height: CGFloat = 64, tint: Color = Theme.decor,
         alpha: Double = Theme.decorAmbientAlpha, rows: Int = 4, amplitude: Double = 5,
         band: (centerFraction: CGFloat, span: CGFloat)? = nil) {
        self.width = width
        self.height = height
        self.tint = tint
        self.alpha = alpha
        self.rows = rows
        self.amplitude = amplitude
        self.band = band
    }

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                Canvas { context, size in
                    let w = Double(size.width), h = Double(size.height)
                    let y0 = Double(band?.centerFraction ?? 0.5) * h
                    let span = Double(band?.span ?? 0)
                    let style = StrokeStyle(lineWidth: Theme.decorLineWidth)
                    let strokeColor = GraphicsContext.Shading.color(tint.opacity(alpha))

                    for k in 0..<rows {
                        let rowOffset = span != 0 ? (Double(k) - Double(rows - 1) / 2) * span / Double(rows) : 0
                        var path = Path()
                        var first = true
                        var px = 0.0
                        while px <= w {
                            let y = y0 + rowOffset
                                + amplitude * sin(px / 34 + Double(k) * 1.9)
                                + amplitude * 0.55 * sin(px / 12.6 + Double(k) * 3.7)
                            let pt = CGPoint(x: px, y: y)
                            if first { path.move(to: pt); first = false } else { path.addLine(to: pt) }
                            px += 2
                        }
                        context.stroke(path, with: strokeColor, style: style)
                    }
                }
                .frame(width: width, height: height)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: - Golden arc (archipelago constellation overlay + About window)

/// The "1945 → 2045" gold arc — draft's `goldenArc(x,w,h,col,alpha,labelCol)`: an ELLIPSE arc
/// (radiusX=w·0.42, radiusY=h·0.72, center BELOW the canvas at y=h·1.28 so only its top dome is
/// visible), spanning angle π·1.12 → π·1.88, with a small dot + a 9pt mono label at each of the
/// TWO endpoints only ("1945"/"2045") — the draft has no intermediate decade ticks. An earlier v1
/// pass used a circular arc with 10-year tick marks; both details were prose-derived guesses that
/// the draft contradicts.
struct GoldenArc: View {
    var width: CGFloat = 260
    var height: CGFloat = 64
    /// Draft: 'main' canvas passes `p.arc`; 'about' passes `p.arc*.8` (scaled down alongside a
    /// shorter effective height, `h*.92`) — exposed here so each call site matches exactly instead
    /// of this view guessing which role it's in.
    var alpha: Double = Theme.decorArcAlpha

    private static let startAngle = Double.pi * 1.12
    private static let endAngle = Double.pi * 1.88

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                Canvas { context, size in
                    let w = Double(size.width), h = Double(size.height)
                    let center = CGPoint(x: w / 2, y: h * 1.28)
                    let rx = w * 0.42, ry = h * 0.72
                    let goldColor = GraphicsContext.Shading.color(Theme.decorGold.opacity(alpha))

                    var arc = Path()
                    let steps = 120
                    for step in 0...steps {
                        let t = Self.startAngle + (Self.endAngle - Self.startAngle) * (Double(step) / Double(steps))
                        let pt = CGPoint(x: center.x + CGFloat(cos(t) * rx), y: center.y + CGFloat(sin(t) * ry))
                        if step == 0 { arc.move(to: pt) } else { arc.addLine(to: pt) }
                    }
                    context.stroke(arc, with: goldColor, lineWidth: 1)

                    let endpoints: [(angle: Double, label: String)] = [(Self.startAngle, "1945"), (Self.endAngle, "2045")]
                    for (angle, label) in endpoints {
                        let px = center.x + CGFloat(cos(angle) * rx)
                        let py = center.y + CGFloat(sin(angle) * ry)
                        let dotRect = CGRect(x: px - 2, y: py - 2, width: 4, height: 4)
                        context.fill(Path(ellipseIn: dotRect), with: goldColor)
                        context.draw(
                            Text(label).font(Theme.scalable(9, design: .monospaced)).foregroundStyle(Theme.decor),
                            at: CGPoint(x: px, y: py - 8),
                            anchor: .bottom
                        )
                    }
                }
                .frame(width: width, height: height)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: - Padi & kapas sprigs (About window)

/// Rice (padi, left — 7 grains) and cotton (kapas, right — 3 boll clusters) sprig line-art,
/// standalone — deliberately NOT the Garuda Pancasila shield these normally flank (guardrail, see
/// file header). Verbatim port of the draft's `sprigs(x,cx,cy,S,col,alpha)`: grain/boll positions
/// come from the draft's own parametrization, not from sampling the stem's bezier curve (an
/// earlier v1 pass used `Path.trimmedPath(...).currentPoint`, which follows the curve but lands
/// grains in different places than the draft's independent formula).
struct PadiKapasSprigs: View {
    var width: CGFloat = 200
    var height: CGFloat = 56
    /// Draft's `S` scale param — fixed at 60 for the one call site (`sprigs(x,w*.5,h*.62,60,...)`).
    var scale: Double = 60
    /// Vertical center as a fraction of the frame height — draft centers at `h*.62` of the SHARED
    /// about-canvas; exposed so a differently-proportioned frame can still match visually.
    var centerYFraction: CGFloat = 0.62

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                Canvas { context, size in
                    let center = CGPoint(x: size.width * 0.5, y: size.height * centerYFraction)
                    drawSprigs(context: context, center: center, S: scale)
                }
                .frame(width: width, height: height)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    private func drawSprigs(context: GraphicsContext, center: CGPoint, S: Double) {
        let alpha = Theme.decorAmbientAlpha + 0.13   // draft: sprigs(..., p.amb+.13)
        let color = GraphicsContext.Shading.color(Theme.decor.opacity(alpha))
        let lineWidth = Theme.decorLineWidth

        func offsetPoint(_ dx: Double, _ dy: Double) -> CGPoint {
            CGPoint(x: center.x + CGFloat(dx), y: center.y + CGFloat(dy))
        }

        // padi (left): curved stem, base→tip.
        var padiStem = Path()
        padiStem.move(to: offsetPoint(-S * 0.55, S * 0.5))
        padiStem.addQuadCurve(to: offsetPoint(-S * 0.38, -S * 0.55), control: offsetPoint(-S * 0.75, -S * 0.15))
        context.stroke(padiStem, with: color, lineWidth: lineWidth)

        // 7 grains — draft's own (bx,by) formula, NOT a sample of the stem curve above.
        for i in 0..<7 {
            let t = 0.35 + Double(i) * 0.09
            let bx = -S * 0.55 + S * 0.17 * (t * 2)
            let by = S * 0.5 - S * 1.05 * t
            let angle = -0.7 + Double(i) * 0.06
            context.drawLayer { layer in
                layer.translateBy(x: center.x + CGFloat(bx), y: center.y + CGFloat(by))
                layer.rotate(by: .radians(angle))
                let grainRect = CGRect(x: -2.4, y: -4.6, width: 4.8, height: 9.2)   // rx=2.4, ry=4.6
                layer.stroke(Path(ellipseIn: grainRect), with: color, lineWidth: lineWidth)
            }
        }

        // kapas (right): curved stem, base→tip.
        var kapasStem = Path()
        kapasStem.move(to: offsetPoint(S * 0.55, S * 0.5))
        kapasStem.addQuadCurve(to: offsetPoint(S * 0.4, -S * 0.5), control: offsetPoint(S * 0.72, -S * 0.1))
        context.stroke(kapasStem, with: color, lineWidth: lineWidth)

        // 3 boll positions, each a 3-circle cluster (a "puff"), draft's fixed offset triplet.
        let bollCenters: [(Double, Double)] = [(S * 0.4, -S * 0.5), (S * 0.58, -S * 0.22), (S * 0.62, S * 0.08)]
        let offsets: [(Double, Double)] = [(0, -3), (3, 2), (-3, 2)]
        for (bx, by) in bollCenters {
            for (ox, oy) in offsets {
                let p = offsetPoint(bx + ox, by + oy)
                let rect = CGRect(x: p.x - 3.6, y: p.y - 3.6, width: 7.2, height: 7.2)
                context.stroke(Path(ellipseIn: rect), with: color, lineWidth: lineWidth)
            }
        }
    }
}

// MARK: - Cartographic squiggle (SearchListView noResults)

/// `.noResults` decoration: a small BROKEN cartographic line — draft's `'broken'` canvas case.
/// Two DASHED sinusoidal segments (`setLineDash([5,4])` — an earlier v1 pass used solid lines) with
/// a gap between them, a filled dot capping each inner end.
struct CartographicSquiggle: View {
    var width: CGFloat = 220
    var height: CGFloat = 90

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                Canvas { context, size in
                    let w = Double(size.width), h = Double(size.height)
                    let alpha = Theme.decorAmbientAlpha + 0.06   // draft: p.amb+.06
                    let color = GraphicsContext.Shading.color(Theme.decor.opacity(alpha))
                    let style = StrokeStyle(lineWidth: 1, dash: [5, 4])

                    func wavySegment(from x0: Double, to x1: Double, yBase: Double, phase: Double) -> Path {
                        var path = Path()
                        var first = true
                        var px = x0
                        while px <= x1 {
                            let y = yBase + 9 * sin(px / 26 + phase)
                            let pt = CGPoint(x: px, y: y)
                            if first { path.move(to: pt); first = false } else { path.addLine(to: pt) }
                            px += 2
                        }
                        return path
                    }

                    // Draft: seg1 x∈[w*.12,w*.42] y=h*.72+9·sin(px/26); seg2 x∈[w*.58,w*.88] y=h*.7+9·sin(px/26+2).
                    let seg1 = wavySegment(from: w * 0.12, to: w * 0.42, yBase: h * 0.72, phase: 0)
                    let seg2 = wavySegment(from: w * 0.58, to: w * 0.88, yBase: h * 0.7, phase: 2)
                    context.stroke(seg1, with: color, style: style)
                    context.stroke(seg2, with: color, style: style)

                    let dot1Center = CGPoint(x: w * 0.42 + 8, y: h * 0.72)
                    let dot2Center = CGPoint(x: w * 0.58 - 8, y: h * 0.7)
                    for c in [dot1Center, dot2Center] {
                        let rect = CGRect(x: c.x - 2.6, y: c.y - 2.6, width: 5.2, height: 5.2)
                        context.fill(Path(ellipseIn: rect), with: color)
                    }
                }
                .frame(width: width, height: height)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: - Archipelago constellation (flagship EmptyDetail .noSelection + reduced .mediaEmpty)

/// The Nusantara coastline motif — draft's `coastDots()` + `ISLANDS`/`BALI`/`proj()`: a dot-per-
/// ~6pt sampling of each island's coastline edges, Bali marked with a filled dot + an accent ring,
/// optionally topped with the gold 1945→2045 arc (`showArc`). Sized via `GeometryReader` so it
/// reflows to whatever width its container proposes (content column ~280–460pt vs full-bleed
/// detail column) rather than a single fixed canvas size.
struct ArchipelagoConstellation: View {
    var showArc: Bool = true
    var height: CGFloat = 200

    /// Approximate island coastlines, lon/lat degree pairs — Sumatra through Papua/Maluku
    /// (guardrail: full archipelago, never a cropped western-only silhouette). Verbatim from the
    /// Zero-approved reference draft's `ISLANDS` array (`kbli-d4-draft.html`), not re-derived.
    private static let islands: [[(lon: Double, lat: Double)]] = [
        [(95.3, 5.6), (97.5, 5.2), (99, 3.5), (100.5, 2), (102, 0.5), (103.5, -1), (104.5, -2.5), (105.8, -4.5), (106, -5.9), (104.5, -5.7), (103, -4.5), (101.5, -3), (100, -1), (98.7, 0.8), (97, 2.5), (95.8, 4), (95.3, 5.6)],
        [(105.2, -6.1), (107, -6), (109, -6.4), (111, -6.4), (113, -6.9), (114.6, -7.2), (114.6, -8.6), (112.5, -8.3), (110, -8), (108, -7.8), (106.2, -7), (105.2, -6.7), (105.2, -6.1)],
        [(114.9, -8.2), (115.6, -8.25), (115.4, -8.75), (114.95, -8.55), (114.9, -8.2)],
        [(116.2, -8.4), (116.75, -8.5), (116.6, -8.95), (116.25, -8.85), (116.2, -8.4)],
        [(117.1, -8.4), (118.3, -8.3), (119.1, -8.8), (118.2, -9), (117.3, -8.9), (117.1, -8.4)],
        [(119.9, -8.5), (121.5, -8.5), (123, -8.75), (122.2, -8.95), (120.6, -8.85), (119.9, -8.5)],
        [(119.4, -9.55), (120.7, -10.1), (120.2, -10.3), (119.4, -9.9), (119.4, -9.55)],
        [(123.8, -10.1), (125.2, -9.3), (126.9, -8.4), (126.2, -8.3), (124.6, -9.2), (123.8, -10.1)],
        [(109.3, 1.6), (111, 1), (113, 1.3), (115, 2.2), (117, 3.6), (118.4, 2.1), (117.4, 0.5), (116.5, -1.5), (116, -3.1), (114.4, -3.7), (112.5, -3.2), (111, -2.8), (110, -1.4), (109, 0.2), (109.3, 1.6)],
        [(119.4, 0.6), (120.6, 1.3), (122, 1), (123.8, 0.9), (125.1, 1.6), (124.4, 0.6), (123, 0.4), (122.4, -1.3), (122.9, -3.4), (122.2, -5.3), (121.6, -4.1), (120.6, -5.7), (119.7, -5.65), (119.3, -4), (119.8, -2), (119.4, 0.6)],
        [(127.4, 1.9), (128.6, 1.2), (128.2, 0.2), (127.6, 0.9), (127.4, 1.9)],
        [(128.5, -3.2), (130.6, -3), (130, -3.5), (128.7, -3.55), (128.5, -3.2)],
        [(126, -3.3), (127.2, -3.2), (127, -3.7), (126.1, -3.6), (126, -3.3)],
        [(131, -0.8), (132.6, -0.5), (133.6, -1.3), (132.8, -2.3), (131.4, -2.5), (130.8, -1.7), (131, -0.8)],
        [(133.9, -1.6), (136, -1.8), (138, -2.2), (140.8, -2.6), (141, -5), (140.9, -8.9), (139, -8), (138.4, -7), (137.5, -5.2), (136, -4.6), (134.9, -3.9), (134, -2.9), (133.9, -1.6)],
    ]
    private static let bali: (lon: Double, lat: Double) = (115.2, -8.5)

    private static func project(_ lon: Double, _ lat: Double, w: Double, h: Double, pad: Double) -> CGPoint {
        CGPoint(x: pad + (lon - 95) / 46 * (w - 2 * pad),
                y: pad + (6 - lat) / 17 * (h - 2 * pad))
    }

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                GeometryReader { geo in
                    ZStack {
                        Canvas { context, size in drawCoastDots(context: context, size: size) }
                        if showArc {
                            GoldenArc(width: geo.size.width, height: geo.size.height)
                        }
                    }
                }
                .frame(height: height)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    private func drawCoastDots(context: GraphicsContext, size: CGSize) {
        let w = Double(size.width), h = Double(size.height)
        // draft: coastDots(x,w,h,44,p.decor,p.focal,...) on the 'main' canvas — but 44 was a FIXED
        // constant there, tuned for that canvas's own size. D4c.1 bug (found via pixel-verified
        // snapshot): `.mediaEmpty` calls this at height:90 — `h - 2*pad = 90 - 88 = 2pt` of vertical
        // room for the ENTIRE latitude range, collapsing the whole archipelago into a near-flat
        // line. Scale pad DOWN for small canvases (never up — 44 stays the ceiling for the normal
        // ~200pt 'main'-sized canvas, matching the draft exactly there).
        let pad = min(44.0, min(w, h) * 0.22)
        let dotRadius = Theme.decorDotRadius
        let dotColor = GraphicsContext.Shading.color(Theme.decor.opacity(Theme.decorFocalAlpha))

        for polygon in Self.islands {
            guard polygon.count > 1 else { continue }
            for i in 0..<(polygon.count - 1) {
                let p1 = Self.project(polygon[i].lon, polygon[i].lat, w: w, h: h, pad: pad)
                let p2 = Self.project(polygon[i + 1].lon, polygon[i + 1].lat, w: w, h: h, pad: pad)
                let dx = Double(p2.x - p1.x), dy = Double(p2.y - p1.y)
                let length = (dx * dx + dy * dy).squareRoot()
                let n = max(1, Int((length / 6).rounded()))
                for j in 0...n {
                    let t = Double(j) / Double(n)
                    let pt = CGPoint(x: p1.x + (p2.x - p1.x) * t, y: p1.y + (p2.y - p1.y) * t)
                    let rect = CGRect(x: pt.x - dotRadius, y: pt.y - dotRadius, width: dotRadius * 2, height: dotRadius * 2)
                    context.fill(Path(ellipseIn: rect), with: dotColor)
                }
            }
        }

        // Bali: filled dot (r=3) + a stroked accent ring (r=6.5, lineWidth .8). The filled dot's
        // alpha is a flat 0.5 in the draft (its `p.dot? .5:.3` ternary is always-truthy on a
        // non-zero number — see Theme.swift's D4 token comment) rather than mode-dependent.
        let baliPt = Self.project(Self.bali.lon, Self.bali.lat, w: w, h: h, pad: pad)
        let baliDotRect = CGRect(x: baliPt.x - 3, y: baliPt.y - 3, width: 6, height: 6)
        context.fill(Path(ellipseIn: baliDotRect), with: .color(Theme.decor.opacity(0.5)))
        let ringRect = CGRect(x: baliPt.x - 6.5, y: baliPt.y - 6.5, width: 13, height: 13)
        context.stroke(Path(ellipseIn: ringRect), with: dotColor, lineWidth: 0.8)
    }
}

// MARK: - Guilloché field (D4d, 2026-08-11 — dense banknote-style texture, replaces sparse bands)

/// Dense woven guilloché field: a real engraved-banknote register reads from DENSITY (many
/// overlapping low-alpha rows), not from any single visible line — `GuillocheBand`'s 2-4 sparse
/// rows read as "two lines", not a texture. Two interleaved phase FAMILIES (alternating rows use a
/// different frequency+direction pair) at low per-row alpha (.05-.07 typical) but high row count —
/// the field emerges from the overlap; no single row shouts.
struct GuillocheField: View {
    var width: CGFloat?
    var height: CGFloat = 150
    var tint: Color = Theme.decor
    var alpha: Double = 0.06
    var rows: Int = 16

    var body: some View {
        Group {
            if Theme.decorationsVisible {
                Canvas { context, size in
                    let w = Double(size.width), h = Double(size.height)
                    let style = StrokeStyle(lineWidth: Theme.decorLineWidth)
                    let color = GraphicsContext.Shading.color(tint.opacity(alpha))
                    for k in 0..<rows {
                        let y0 = rows > 1 ? (Double(k) / Double(rows - 1)) * h : h / 2
                        let amp = 3.0 + 2.0 * Double(k % 3) / 2.0   // staggered 3-5px
                        let family = k % 2
                        let (f1, f2, dir): (Double, Double, Double) = family == 0
                            ? (34.0, 12.6, 1.0) : (27.0, 15.8, -1.0)
                        var path = Path()
                        var first = true
                        var px = 0.0
                        while px <= w {
                            let y = y0
                                + amp * sin(dir * px / f1 + Double(k) * 1.9)
                                + amp * 0.55 * sin(dir * px / f2 + Double(k) * 3.7)
                            let pt = CGPoint(x: px, y: y)
                            if first { path.move(to: pt); first = false } else { path.addLine(to: pt) }
                            px += 2
                        }
                        context.stroke(path, with: color, style: style)
                    }
                }
                .frame(width: width, height: height)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

