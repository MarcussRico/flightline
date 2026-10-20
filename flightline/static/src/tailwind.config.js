// Styles are prebuilt into ../app.css so the demo needs no build step and no network.
// Rebuild after editing index.html:  npx tailwindcss@3.4.17 -c flightline/static/src/tailwind.config.js \
//   -i flightline/static/src/input.css -o flightline/static/app.css --minify
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
module.exports = {
  content: ["./flightline/static/index.html"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"), panel: v("panel"), subtle: v("subtle"), line: v("line"), "line-strong": v("line-strong"),
        fg: v("fg"), "fg-2": v("fg-2"), "fg-3": v("fg-3"),
        plan: v("plan"), practice: v("practice"),
        spares: v("spares"), depot: v("depot"), removal: v("removal"), grounded: v("grounded"), planned: v("planned"),
      },
      fontFamily: {
        sans: ["Geist", "system-ui", "-apple-system", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "monospace"],
      },
      fontSize: { "2xs": ["11px", "16px"] },
      boxShadow: { card: "0 1px 2px rgb(16 24 40 / 0.04)", pop: "0 12px 32px -8px rgb(16 24 40 / 0.25)" },
    },
  },
  plugins: [],
};
