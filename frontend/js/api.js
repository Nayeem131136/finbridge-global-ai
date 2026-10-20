/* Shared client state + fetch helper. The session cookie is HttpOnly (JavaScript cannot read it);
   the CSRF token lives only in memory and is re-fetched from /api/auth/me on every page load. */
export const state = { auth: null, csrf: null, sessionId: null, lang: "en", health: null };
const API = new URLSearchParams(location.search).get("api") || "";

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && state.csrf) headers["X-CSRF-Token"] = state.csrf;
  let r;
  try {
    r = await fetch(API + path, { method, headers, credentials: "same-origin", body: body !== undefined ? JSON.stringify(body) : undefined });
  } catch (_) {
    throw new ApiError("Cannot reach the server. Check that it is running, then try again.", 0);
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : `Request failed (${r.status})`;
    if (r.status === 401 && state.auth) { state.auth = null; state.csrf = null; window.dispatchEvent(new CustomEvent("fb:signed-out")); }
    throw new ApiError(detail, r.status);
  }
  return data;
}
export const get = (p) => api(p);
export const post = (p, b = {}) => api(p, { method: "POST", body: b });
export const put = (p, b) => api(p, { method: "PUT", body: b });
export const del = (p) => api(p, { method: "DELETE" });
export const signedIn = () => !!state.auth;
