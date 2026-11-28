const LOGIN = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/;
const ERRORS = new Set(["busy", "invalid_login", "lookup_failed", "rate_limited", "unavailable", "upstream_unavailable"]);

function record(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function day(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw Error("Invalid day");
  const parsed = new Date(value + "T00:00:00Z");
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) throw Error("Invalid day");
  return parsed.getTime();
}

export function validatePreview(value, login, { caps, stages }) {
  if (!record(value) || value.schema_version !== 1 || !record(value.subject) || !record(value.counts) || !record(value.settings)) throw Error("Invalid preview");
  const { subject, settings, counts } = value;
  if (
    typeof subject.login !== "string" ||
    !LOGIN.test(subject.login) ||
    subject.login.toLowerCase() !== login.toLowerCase() ||
    typeof subject.id !== "string" ||
    !/^[A-Za-z0-9_=-]{1,200}$/.test(subject.id) ||
    settings.key !== `island-seed-v1:${subject.id}` ||
    !stages.includes(settings.stage)
  )
    throw Error("Invalid identity");
  if (
    day(value.activity_end) - day(value.activity_start) !== 30 * 86400000 ||
    typeof value.observed_at !== "string" ||
    !/(Z|\+00:00)$/.test(value.observed_at) ||
    !Number.isFinite(Date.parse(value.observed_at)) ||
    new Date(value.observed_at).toISOString().slice(0, 10) !== value.activity_end ||
    typeof value.excluded_repository !== "string" ||
    !/^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(value.excluded_repository)
  )
    throw Error("Invalid observation");
  const safeSettings = { key: settings.key, stage: settings.stage };
  const safeCounts = {};
  for (const [name, cap] of Object.entries(caps)) {
    if (
      !Number.isSafeInteger(counts[name]) ||
      counts[name] < 0 ||
      !Number.isFinite(settings[name]) ||
      settings[name] < 0 ||
      settings[name] > 1 ||
      Math.abs(settings[name] - Math.min(1, Math.log1p(counts[name]) / Math.log1p(cap))) > 1e-12
    )
      throw Error("Invalid signals");
    safeSettings[name] = settings[name];
    safeCounts[name] = counts[name];
  }
  if (counts.outside > counts.prs + counts.issues) throw Error("Invalid outside count");
  return {
    activity_end: value.activity_end,
    activity_start: value.activity_start,
    counts: safeCounts,
    excluded_repository: value.excluded_repository,
    observed_at: value.observed_at,
    schema_version: 1,
    settings: safeSettings,
    subject: { id: subject.id, login: subject.login },
  };
}

export function sceneHash(state, signals) {
  const params = new URLSearchParams();
  params.set("stage", state.stage);
  for (const name of signals) params.set(name, String(state[name]));
  params.set("key", state.key);
  if (state.poster) params.set("poster", "1");
  return params.toString();
}

export function createLookup({ baseUrl, rules, onResult, onStatus, fetcher = fetch }) {
  let generation = 0;
  let active = null;
  function cancel(code = "canceled") {
    generation += 1;
    if (active) {
      clearTimeout(active.timer);
      active.controller.abort();
      active = null;
      if (code) onStatus({ code });
    }
  }
  async function load(input) {
    cancel(null);
    const login = input.trim();
    if (!baseUrl) {
      onStatus({ code: "unavailable" });
      return;
    }
    if (!LOGIN.test(login)) {
      onStatus({ code: "invalid_login" });
      return;
    }
    const current = generation;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      if (current === generation) cancel("timeout");
    }, 75000);
    active = { controller, timer };
    onStatus({ code: "loading", login });
    try {
      const response = await fetcher(`${baseUrl}/preview?login=${encodeURIComponent(login)}`, {
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
        signal: controller.signal,
      });
      if (current !== generation) return;
      if (response.status === 429) {
        onStatus({ code: "rate_limited" });
        return;
      }
      const text = await response.text();
      if (current !== generation) return;
      if (text.length > 10000) throw Error("Oversize preview");
      const payload = JSON.parse(text);
      if (!response.ok) {
        const code = ERRORS.has(payload?.error?.code) ? payload.error.code : "lookup_failed";
        onStatus({ code });
        return;
      }
      const result = validatePreview(payload, login, rules);
      onResult(result);
      onStatus({ code: "success", login: result.subject.login });
    } catch {
      if (current === generation) onStatus({ code: "lookup_failed" });
    } finally {
      clearTimeout(timer);
      if (current === generation) active = null;
    }
  }
  return { cancel, load };
}
