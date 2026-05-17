// Tailwind v4 ships its PostCSS plugin in a separate package
// (@tailwindcss/postcss). The hoisted root node_modules now has Tailwind v4
// even though apps/admin-dashboard-local/package.json declares v3 — using
// the wrapper plugin works for both v3 globals.css (utility classes) and the
// cockpit-shell.css (plain CSS, ignored by the plugin).
module.exports = {
  plugins: {
    "@tailwindcss/postcss": {},
    autoprefixer: {},
  },
};
