const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    const message = (data && data.error) || `Request failed (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return data;
}

// Same-origin proxy for the "today's challenge" image (the upstream S3 URL is
// presigned and CORS-less, so the backend streams the bytes). Usable directly as
// an <img src> and for a blob download.
export const shareImageUrl = (day, language = "english") =>
  `${BASE}/api/days/${encodeURIComponent(day)}/share-image/?language=${encodeURIComponent(language)}`;

export const api = {
  health: () => request("/health/"),
  getDay: (day, language = "english") =>
    request(`/days/${day}/?language=${encodeURIComponent(language)}`),
  verseSummary: (payload) =>
    request("/verse-summary/", { method: "POST", body: JSON.stringify(payload) }),
  generateScript: (payload) =>
    request("/script/", { method: "POST", body: JSON.stringify(payload) }),
  generateStructure: (payload) =>
    request("/structure/", { method: "POST", body: JSON.stringify(payload) }),
  generateAudio: (payload) =>
    request("/audio/", { method: "POST", body: JSON.stringify(payload) }),
};
