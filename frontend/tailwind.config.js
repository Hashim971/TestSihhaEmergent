/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        sand: "#FBFBF9",
        surface: "#FFFFFF",
        forest: "rgb(var(--brand-primary) / <alpha-value>)",
        "forest-hover": "rgb(var(--brand-primary) / 0.85)",
        sage: "rgb(var(--brand-accent) / <alpha-value>)",
        terracotta: "#E06D53",
        ink: "#1A1A1A",
        "ink-soft": "#525252",
        line: "#E5E4E2",
      },
      fontFamily: {
        heading: ["Outfit", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"],
      },
    },
  },
  plugins: [],
};
