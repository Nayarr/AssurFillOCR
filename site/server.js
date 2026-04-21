/**
 * server.js — Serveur de test minimaliste
 * Sert form.html + style.css sur http://localhost:3000
 * Lance avec : node server.js
 */

const http = require("http");
const fs   = require("fs");
const path = require("path");

const PORT = 3000;
const ROOT = __dirname; // dossier où se trouvent form.html et style.css

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css":  "text/css; charset=utf-8",
  ".js":   "application/javascript",
  ".json": "application/json",
  ".ico":  "image/x-icon",
};

const server = http.createServer((req, res) => {
  // Normalise l'URL : "/" → "/form.html"
  let urlPath = req.url.split("?")[0];
  if (urlPath === "/") urlPath = "/form.html";

  const filePath = path.join(ROOT, urlPath);
  const ext      = path.extname(filePath).toLowerCase();
  const mimeType = MIME[ext] || "application/octet-stream";

  // Sécurité basique : on reste dans ROOT
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    return res.end("Forbidden");
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (err.code === "ENOENT") {
        res.writeHead(404, { "Content-Type": "text/plain" });
        return res.end(`404 — Fichier introuvable : ${urlPath}`);
      }
      res.writeHead(500);
      return res.end("Erreur serveur");
    }
    res.writeHead(200, { "Content-Type": mimeType });
    res.end(data);
  });

  // Log simple dans la console
  console.log(`[${new Date().toLocaleTimeString()}]  ${req.method}  ${req.url}`);
});

server.listen(PORT, () => {
  console.log(`\n✅  Serveur démarré → http://localhost:${PORT}\n`);
  console.log("   Placez form.html et style.css dans le même dossier que server.js");
  console.log("   Arrêt : Ctrl+C\n");
});