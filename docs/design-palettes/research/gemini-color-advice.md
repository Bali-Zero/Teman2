Here is a critical, senior-level design review of the Bali Zero dashboard prototype, answering your specific questions based on the CSS implementation and modern UI standards.

### 1. BACKGROUND Darkness Level
**Do not use `#1a1a1a` for the base background.**
In a modern UI utilizing frosted glass, inner light leaks, and aurora gradients, raising the base to `#1a1a1a` washes out your contrast ratios and muddies the `mix-blend-mode: screen` effects. It makes the app look "dusty" rather than sleek.
*   **Linear** sits around `#080808`.
*   **Raycast** uses `#0d0d0d`.
*   **Vercel** uses pure `#000000` to make elevated surfaces pop.

**Recommendation:** Keep the canvas at **`#0a0a0a`** (or shift microscopically to `#0c0c0c` for a hint of warmth). If the dashboard feels "too dark," the solution is to elevate the *surfaces* (cards, sidebars) and increase their lightness, not to brighten the void behind them.

### 2. Per-Surface Hierarchy
To maintain depth on a `#0a0a0a` base, you need a strict, mathematically sound elevation scale. The current CSS is close but needs refinement for hover/active states. Use this exact hierarchy:
*   **Body Wrapper (Canvas):** `#0a0a0a`
*   **Sidebar:** `#0f0f0f` (subtly lifted from the canvas to define the application shell).
*   **Dashboard Main Content:** Transparent (letting the `#0a0a0a` canvas show through).
*   **Cards (Frosted Glass):** `rgba(20, 20, 20, 0.65)` (equivalent to `#141414` at 65%).
*   **Elevated Surfaces (Modals, Dropdowns):** `#1c1c1e` (solid, no blur) + `box-shadow: 0 20px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.1)`.
*   **Hover State:** `#262626` (or `rgba(255,255,255,0.08)` for translucent elements).
*   **Active/Pressed State:** `#171717` (Active states should depress *down* into the z-axis, making them darker than the hover state, not lighter).

### 3. Card Background Contexts
A single card style cannot serve three vastly different cognitive modes. Apply these specific treatments:
*   **Workspace Dashboard (Dense Data):** Avoid backdrop blurs entirely. Blurs cause GPU overhead and distract from dense typography. Use a solid **`#121212`** with a crisp `1px solid rgba(255,255,255,0.06)`.
*   **Portal (Airy/Client-Facing):** Use your current `.bz-glass`. `rgba(20, 20, 20, 0.65)` with `backdrop-filter: blur(24px)`. It feels premium and welcoming.
*   **Marketing (Editorial):** Maximum visual impact. Use `rgba(10, 10, 10, 0.4)` over the aurora gradients, utilizing the `.bz-gborder` mouse-aware glow border to create interactive discovery.

### 4. Signal Red `#ff2d4c`
`#ff2d4c` is an excellent, high-energy brand accent, but it is too aggressive for filled interactive surfaces on `#0a0a0a` (it will cause retina burn/halation). Do not shift to magenta (`#f01946`) or neon pink (`#ff3356`).
**Recommendation:** Split the token by usage.
*   **Borders, Glows, Accents:** Keep **`#ff2d4c`**.
*   **Primary Buttons (Filled):** Shift down to **`#e62140`**. This anchors the button and prevents it from vibrating against the dark background.
*   **Primary Text (Links):** Shift up/desaturate slightly to **`#ff5c77`** to pass WCAG AAA contrast without eye strain.

### 5. Category Hue Set
Your current set has a fatal flaw: **"Living" uses `#ff2d4c`**, which hijacks the primary brand action color. A category should never compete with a primary CTA. Furthermore, Visa (`#4a8ec4`) and Emerging (`#4ab8c4`) are too close together (blue vs. cyan).
**Proposed Refined Set:**
*   Visa: **`#3b82f6`** (Clear Blue)
*   Business: **`#10b981`** (Emerald)
*   Tax: **`#eab308`** (Golden Yellow — easier to read than muddy gold)
*   Property: **`#8b5cf6`** (Indigo/Violet)
*   Living: **`#f97316`** (Sunset Orange — distinct from your brand red)
*   Emerging: **`#06b6d4`** (Cyan — pulls safely away from Visa's blue)

### 6. State Colors (Kanban)
The Tailwind 400-500 colors (`#fb923c`, `#3b82f6`, etc.) are too saturated for a sophisticated dark UI. High-saturation states compete with your data and make the app look like a toy. Shift them to deeper "jewel" tones:
*   Inquiry: **`#8a8f98`** (Dusty gray)
*   Wait: **`#d97706`** (Deep amber, less neon)
*   Invoice: **`#ca8a04`** (Deep gold. Yellow `#facc15` is notoriously unreadable with white text)
*   Active: **`#2563eb`** (Royal blue)
*   Done: **`#16a34a`** (Grassy green, not neon)
*   Fail: **`#dc2626`** (Crimson)

### 7. Aurora Body Gradient
Four rotating conic radials with `mix-blend-mode: screen` look phenomenal for a marketing site but are **toxic for a SaaS workspace**. They cause cognitive fatigue, reduce text contrast, and trigger constant GPU repaints.
**Recommendation:**
*   **Marketing/Portal:** Keep the animation, but drop the opacity from ~20% to **`12%`**.
*   **Workspace:** Turn off the animation entirely (`animation: none`). Pin the radials to the extreme top corners or behind the sidebar, and drop the opacity to **`4-6%`**. It should feel like a static, atmospheric light leak, not a disco ball.

### 8. The 2 Tab Bar Issue (Overflow-x)
Using `overflow-x: auto` with a gradient mask for primary desktop navigation is an anti-pattern. Users have zero "scent of information" for hidden tabs (like KBLI), and horizontal scrolling on a mouse is frustrating.
**Recommendation:** Implement the **Priority+ Pattern**. Show the first 4 tabs that fit naturally, and collapse the rest into a `More ▼` dropdown button.
Alternatively, if this is a true Workspace app, **abandon horizontal tabs entirely** for the main nav. Move the navigation to a left-hand vertical sidebar (like Linear or Notion). Vertical sidebars scale to dozens of items effortlessly and free up the top bar for page-specific context and a Cmd-K search trigger.

### 9. Metallic Text Three-Stop
Your current gradient (`#f5f5f5` → `#a8a8a8` → `#f5f5f5` → `#5a5a5a`) jumps too harshly at the end. The severe drop to `#5a5a5a` creates banding that looks like 2000s-era WordArt or skeuomorphic iOS 6 chrome. It feels cheap, not premium.
**Recommendation:** Modern metallic text relies on high contrast but smooth transitions. Use a diagonal sweep with softer stops:
```css
background: linear-gradient(135deg, #ffffff 0%, #a1a1aa 50%, #e4e4e7 100%);
```
This creates a smooth, brushed titanium look without the aggressive banding.

### 10. The Missing Color
You are missing two critical tokens that elevate a dashboard from "good" to "can ship":
1.  **A Focus Ring / Outline Color (`--bz-focus-ring`):** Relying on your signal red (`--bz-primary`) for focus states on neutral elements (like standard text inputs or dropdowns) makes the app feel like it's screaming at the user or indicating an error. Add a neutral focus ring: **`rgba(255, 255, 255, 0.25)`**.
2.  **A Subtle Interactive Layer (`--bz-surface-muted`):** You need a background color specifically for secondary buttons, table row hovers, or empty states. The jump from the `#0a0a0a` canvas to your `#141414` surface is too heavy for subtle interactions. Add **`rgba(255, 255, 255, 0.04)`** as a transparent interactive token.
