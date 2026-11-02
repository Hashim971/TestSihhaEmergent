const fs = require("fs");
const path = require("path");

const url = process.argv[2] || process.env.SIHHA_APP_URL;
if (!url || !url.startsWith("https://")) {
  console.error("Usage: npm run set-url -- https://your-app-address");
  process.exit(1);
}
const file = path.join(__dirname, "..", "capacitor.config.json");
const config = JSON.parse(fs.readFileSync(file, "utf8"));
config.server.url = url.replace(/\/$/, "");
fs.writeFileSync(file, JSON.stringify(config, null, 2) + "\n");
console.log(`App will open ${config.server.url}`);
