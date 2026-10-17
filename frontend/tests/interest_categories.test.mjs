import test from "node:test";
import assert from "node:assert/strict";
import { interestChoices, INTEREST_CATEGORIES } from "../js/interest_categories.js";

test("exactly three optional goals support multiple selections with Transfer first", () => {
  assert.deepEqual(INTEREST_CATEGORIES.map(([key]) => key), ["transfer", "career and scholarships", "campus life"]);
  assert.deepEqual(interestChoices(["transfer", "campus life"]).filter(item => item.selected).map(item => item.value), ["transfer", "campus life"]);
  assert.equal(interestChoices().some(item => item.selected), false);
});

test("previous categories merge without adding extra choices", () => {
  const choices = interestChoices(["research and projects", "photography", "art and design", "ceramics"]);
  assert.equal(choices.length, 3);
  assert.equal(choices.find(item => item.value === "career and scholarships").selected, true);
  assert.equal(choices.filter(item => item.value === "campus life" && item.selected).length, 1);
});
