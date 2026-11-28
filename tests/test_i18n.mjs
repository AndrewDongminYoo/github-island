import assert from "node:assert/strict";
import test from "node:test";
import { dictionaries, initialLanguage, saveLanguage, translate } from "../playground/i18n.js";

test("saved choice wins; otherwise use the browser language with an English fallback", () => {
  assert.equal(initialLanguage({ getItem: () => "en" }, "ko-KR"), "en");
  assert.equal(initialLanguage({ getItem: () => null }, "ko-KR"), "ko");
  assert.equal(initialLanguage({ getItem: () => "invalid" }, "fr-FR"), "en");
  assert.equal(initialLanguage(null, "kok-IN"), "en");
  assert.equal(initialLanguage({ getItem: () => { throw Error("blocked"); } }, "ko"), "ko");
  assert.doesNotThrow(() => saveLanguage({ setItem: () => { throw Error("blocked"); } }, "ko"));
});

test("both languages cover all messages and preserve interpolation", () => {
  assert.deepEqual(Object.keys(dictionaries.ko).sort(), Object.keys(dictionaries.en).sort());
  assert.equal(translate("ko", "lookup.loading", { login: "octocat" }).includes("octocat"), true);
  assert.equal(translate("en", "action.preview"), "Preview my island");
  assert.equal(translate("ko", "action.preview"), "내 섬 보기");
  assert.notEqual(translate("ko", "lookup.rate_limited"), translate("en", "lookup.rate_limited"));
});
