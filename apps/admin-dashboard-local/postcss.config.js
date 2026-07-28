// Tailwind v4: the compiler is its own PostCSS plugin and vendor-prefixes on
// its own, so `tailwindcss` is no longer a direct plugin here and autoprefixer
// is redundant. Same shape as apps/mouth, which crossed to v4 earlier.
module.exports = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
