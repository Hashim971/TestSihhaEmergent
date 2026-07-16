const path = require("path");

module.exports = {
  devServer: {
    allowedHosts: "all",
  },
  webpack: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
};
