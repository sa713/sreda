import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { DatabaseSync } from "node:sqlite";

const catalog = JSON.parse(readFileSync(new URL("./data/catalog.json", import.meta.url), "utf8"));
const slugs = catalog.flatMap(({ articles }) => articles.map(({ url }) => url.split("/")[2]));
const db = new DatabaseSync(process.env.SREDA_DB ?? "metrics.sqlite3");

db.exec(`
  PRAGMA journal_mode = WAL;
  PRAGMA busy_timeout = 2000;

  CREATE TABLE IF NOT EXISTS views (
    slug TEXT PRIMARY KEY,
    total INTEGER NOT NULL
  ) STRICT;

  CREATE TABLE IF NOT EXISTS votes (
    slug TEXT NOT NULL,
    visitor TEXT NOT NULL,
    PRIMARY KEY (slug, visitor)
  ) STRICT, WITHOUT ROWID;
`);

const loadViews = db.prepare("SELECT slug, total FROM views");
const loadVotes = db.prepare("SELECT slug, COUNT(*) AS total, MAX(visitor = ?) AS selected FROM votes GROUP BY slug");
const getVotes = db.prepare("SELECT COUNT(*) AS total FROM votes WHERE slug = ?");
const recordView = db.prepare(`
  INSERT INTO views (slug, total) VALUES (?, 1)
  ON CONFLICT(slug) DO UPDATE SET total = total + 1
`);
const addVote = db.prepare("INSERT INTO votes (slug, visitor) VALUES (?, ?) ON CONFLICT DO NOTHING");
const removeVote = db.prepare("DELETE FROM votes WHERE slug = ? AND visitor = ?");

const cookieName = "sreda_visitor";
const cookiePattern = /(?:^|;\s*)sreda_visitor=([a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12})(?:;|$)/;

function visitorId(request) {
  return request.headers.cookie?.match(cookiePattern)?.[1];
}

function statsFor(visitor) {
  const result = Object.fromEntries(slugs.map((slug) => [slug, { views: 0, helpful: 0, voted: false }]));
  for (const { slug, total } of loadViews.all()) {
    if (Object.hasOwn(result, slug)) result[slug].views = total;
  }
  for (const { slug, total, selected } of loadVotes.all(visitor)) {
    if (Object.hasOwn(result, slug)) {
      result[slug].helpful = total;
      result[slug].voted = Boolean(selected);
    }
  }
  return result;
}

function json(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

const server = createServer((request, response) => {
  response.setHeader("Cache-Control", "no-store");
  const { method, url } = request;
  try {
    if (method === "GET" && url === "/api/metrics") {
      let visitor = visitorId(request);
      if (!visitor) {
        visitor = randomUUID();
        response.setHeader(
          "Set-Cookie", `${cookieName}=${visitor}; Path=/api/metrics; Max-Age=31536000; HttpOnly; SameSite=Lax`,
        );
      }
      return json(response, 200, statsFor(visitor));
    }

    const route = /^\/api\/metrics\/([a-z0-9-]+)\/(view|helpful)$/.exec(url);
    if (!route || !slugs.includes(route[1])) return json(response, 404, { error: "not_found" });

    const [, slug, action] = route;
    // An ordinary cross-origin form cannot send this header.
    if (request.headers["x-sreda-request"] !== "1") {
      return json(response, 403, { error: "request_header_required" });
    }
    if (action === "view" && method === "POST") {
      recordView.run(slug);
      response.writeHead(204).end();
      return;
    }
    if (action === "helpful" && (method === "PUT" || method === "DELETE")) {
      const visitor = visitorId(request);
      if (!visitor) return json(response, 400, { error: "visitor_cookie_required" });

      const voted = method === "PUT";
      (voted ? addVote : removeVote).run(slug, visitor);
      return json(response, 200, { helpful: getVotes.get(slug).total, voted });
    }
    return json(response, 405, { error: "method_not_allowed" });
  } catch (error) {
    console.error(error);
    return json(response, 500, { error: "metrics_unavailable" });
  }
});

server.listen(8000, "0.0.0.0");
