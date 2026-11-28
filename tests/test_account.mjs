import assert from "node:assert/strict";
import test from "node:test";
import { createLookup, sceneHash, validatePreview } from "../playground/account.js";

const rules = { caps: { prs: 30, reviews: 60, issues: 20, outside: 10, stars: 500, forks: 100 }, stages: ["seed", "sprout", "grove", "mature", "sanctuary"] };
function result() {
  return {
    schema_version: 1,
    subject: { id: "U1", login: "octocat" },
    activity_start: "2026-10-29",
    activity_end: "2026-11-28",
    observed_at: "2026-11-28T12:00:00+00:00",
    excluded_repository: "owner/island",
    counts: { prs: 1, reviews: 0, issues: 0, outside: 0, stars: 0, forks: 0 },
    settings: { prs: 0.20184908658209985, reviews: 0, issues: 0, outside: 0, stars: 0, forks: 0, stage: "seed", key: "island-seed-v1:U1" },
  };
}
function reply(body = result(), status = 200) {
  return new Response(JSON.stringify(body), { status });
}
function deferred() {
  let resolve;
  const promise = new Promise(done => {
    resolve = done;
  });
  return { promise, resolve };
}

test("validates identity, complete dates, safe counts, and all signals before applying", () => {
  assert.deepEqual(validatePreview(result(), "Octocat", rules).settings, result().settings);
  const mutations = [
    value => {
      value.settings.prs = NaN;
    },
    value => {
      delete value.settings.issues;
    },
    value => {
      value.settings.key = "wrong";
    },
    value => {
      value.settings.stage = "unknown";
    },
    value => {
      value.subject.login = "other";
    },
    value => {
      value.activity_start = "2026-11-01";
    },
    value => {
      value.counts.prs = -1;
    },
    value => {
      value.settings.prs = 0;
    },
    value => {
      value.observed_at = "2026-11-27T12:00:00Z";
    },
  ];
  for (const mutate of mutations) {
    const value = result();
    mutate(value);
    assert.throws(() => validatePreview(value, "octocat", rules));
  }
});

test("settings links preserve full signal precision and versioned keys", () => {
  const settings = { ...result().settings, key: "island-seed-v1:" + "a".repeat(100), poster: true };
  const params = new URLSearchParams(sceneHash(settings, Object.keys(rules.caps)));
  assert.equal(Number(params.get("prs")), settings.prs);
  assert.equal(params.get("key"), settings.key);
  assert.equal(params.get("poster"), "1");
  assert.equal(params.has("login"), false);
});

test("fetch uses the fixed service and never browser credentials", async () => {
  const applied = [],
    statuses = [];
  const lookup = createLookup({
    baseUrl: "https://preview.example.test",
    rules,
    fetcher: async (url, options) => {
      assert.equal(url, "https://preview.example.test/preview?login=octocat");
      assert.equal(options.credentials, "omit");
      assert.equal(options.redirect, "error");
      return reply();
    },
    onResult: value => applied.push(value),
    onStatus: value => statuses.push(value.code),
  });
  await lookup.load(" octocat ");
  assert.equal(applied.length, 1);
  assert.deepEqual(statuses, ["loading", "success"]);
});

test("canceling an ignored abort prevents a late response from applying", async () => {
  const pending = deferred(),
    applied = [],
    statuses = [];
  const lookup = createLookup({
    baseUrl: "https://example.test",
    rules,
    fetcher: () => pending.promise,
    onResult: value => applied.push(value),
    onStatus: value => statuses.push(value.code),
  });
  const work = lookup.load("octocat");
  lookup.cancel();
  pending.resolve(reply());
  await work;
  assert.equal(applied.length, 0);
  assert.deepEqual(statuses, ["loading", "canceled"]);
});

test("a newer lookup wins when an older response arrives last", async () => {
  const first = deferred(),
    applied = [];
  let calls = 0;
  const lookup = createLookup({
    baseUrl: "https://example.test",
    rules,
    fetcher: () => (++calls === 1 ? first.promise : Promise.resolve(reply())),
    onResult: value => applied.push(value),
    onStatus: () => {},
  });
  const old = lookup.load("octocat");
  await lookup.load("octocat");
  first.resolve(reply());
  await old;
  assert.equal(applied.length, 1);
});

test("errors preserve the scene and ignore untrusted upstream message text", async () => {
  for (const response of [reply({ error: { code: "rate_limited", message: "SECRET" } }, 429), reply({}), new Response("invalid")]) {
    const applied = [],
      statuses = [];
    const lookup = createLookup({
      baseUrl: "https://example.test",
      rules,
      fetcher: async () => response,
      onResult: value => applied.push(value),
      onStatus: value => statuses.push(value),
    });
    await lookup.load("octocat");
    assert.equal(applied.length, 0);
    assert.notEqual(statuses.at(-1).code, "success");
    assert.equal(JSON.stringify(statuses).includes("SECRET"), false);
  }
});

test("unconfigured service and invalid login do not fetch", async () => {
  const statuses = [];
  const options = { rules, fetcher: () => assert.fail("unexpected fetch"), onResult: () => assert.fail("unexpected result"), onStatus: value => statuses.push(value.code) };
  await createLookup({ ...options, baseUrl: "" }).load("octocat");
  await createLookup({ ...options, baseUrl: "https://example.test" }).load("a--b");
  assert.deepEqual(statuses, ["unavailable", "invalid_login"]);
});

test("provider throttling preserves the scene and asks for a retry without an app error body", async () => {
  for (const body of ['{"Message":"Rate exceeded"}', "Too Many Requests"]) {
    const statuses = [];
    const lookup = createLookup({
      baseUrl: "https://example.test",
      rules,
      fetcher: async () => new Response(body, { status: 429 }),
      onResult: () => assert.fail("unexpected result"),
      onStatus: value => statuses.push(value.code),
    });
    await lookup.load("octocat");
    assert.deepEqual(statuses, ["loading", "rate_limited"]);
  }
});
