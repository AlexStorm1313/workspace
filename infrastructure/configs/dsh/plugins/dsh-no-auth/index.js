import { createHash, createHmac } from "node:crypto";
export const name = "no-auth";
const LOOPBACK = new Set(["127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"]);

function mintCookie(auth, headers, secure) {
  const host = headers.host;
  if (!host) return undefined;
  const authority = secure ? `https://${host}` : host;
  const issuedAt = Date.now(), expiresAt = issuedAt + auth.maxAgeMilliseconds;
  const body = Buffer.from(JSON.stringify({ version: 1, authority, issuedAt, expiresAt })).toString("base64url");
  const sign = Buffer.from(createHmac("sha256", auth.secret).update(body).digest()).toString("base64url");
  const name = "dsh-auth-" + Buffer.from(createHash("sha256").update(authority).digest()).toString("base64url");
  const sec = secure || headers["x-forwarded-proto"]?.includes("https") ? "; Secure" : "";
  return `${name}=v1.${body}.${sign}; Max-Age=${Math.floor(auth.maxAgeMilliseconds / 1000)}; Path=/; HttpOnly; SameSite=Strict${sec}`;
}

export function apply(ctx, config) {
  const allow = new Set((config?.allowHosts || []).map(h => h.toLowerCase()));
  ctx.inject(["connection"], ({ connection }) => {
    const auth = connection.browserAuth;
    const rawAuth = auth.authorizeIndex.bind(auth);
    auth.authorizeIndex = (req, res, sec = false) => {
      if (auth.isAuthenticated(req, sec)) return rawAuth(req, res, sec);
      const host = (req.headers.host || "").split(":")[0].toLowerCase();
      if ((LOOPBACK.has(host) || allow.has(req.headers.host?.toLowerCase())) && connection.isTrusted(req)) {
        const ck = mintCookie(auth, req.headers, sec);
        if (ck) { res.setHeader("set-cookie", ck); res.setHeader("cache-control", "no-store"); return true; }
      }
      return rawAuth(req, res, sec);
    };
  });
}
