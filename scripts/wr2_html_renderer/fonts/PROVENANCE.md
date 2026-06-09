# Vendored fonts — provenance & license

Per reuse-first §4 (license gate) + §7 (provenance tracking).

| File                    | Source                                                         | License     |
| ----------------------- | -------------------------------------------------------------- | ----------- |
| `montserrat-700.woff2`  | fontsource CDN (`montserrat@latest/latin-700-normal.woff2`)    | SIL OFL 1.1 |
| `montserrat-800.woff2`  | fontsource CDN (`montserrat@latest/latin-800-normal.woff2`)    | SIL OFL 1.1 |
| `ibmplexmono-400.woff2` | fontsource CDN (`ibm-plex-mono@latest/latin-400-normal.woff2`) | SIL OFL 1.1 |
| `ibmplexmono-700.woff2` | fontsource CDN (`ibm-plex-mono@latest/latin-700-normal.woff2`) | SIL OFL 1.1 |

Fetched 2026-06-07. SIL OFL 1.1 permits embedding/redistribution — vendoring OK.
Latin subset only (matches brand text; carousels are EN/ID Latin script).

WHY vendored (not Google-Fonts @import): determinism + offline (Law 6). See
`_fonts.css` header and `renderer.py` gap-#4 note.
