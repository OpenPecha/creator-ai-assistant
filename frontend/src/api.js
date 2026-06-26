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
    throw new Error(message);
  }
  return data;
}

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
