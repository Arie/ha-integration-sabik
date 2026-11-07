import { build } from "esbuild";

await build({
  entryPoints: ["src/sabik-card.js"],
  outfile: "../custom_components/sabik/frontend/sabik-card.js",
  bundle: true,
  format: "esm",
  minify: false,
  legalComments: "inline",
  logLevel: "info",
});
