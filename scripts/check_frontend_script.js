const fs = require("fs");

const html = fs.readFileSync("frontend/index.html", "utf8");
const match = html.match(/<script>([\s\S]*)<\/script>/);
if (!match) {
  throw new Error("script not found");
}

new Function(match[1]);
console.log("frontend script ok");
