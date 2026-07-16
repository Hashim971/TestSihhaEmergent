/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        sand: "#FBFBF9",
        surface: "#FFFFFF",
        forest: "#1E3F2A",
        "forest-hover": "#2C5A3D",
        sage: "#B1D8B7",
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
