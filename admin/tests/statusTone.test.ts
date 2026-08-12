import { describe, expect, it } from "vitest";
import { statusTone } from "@/ui/primitives";

/**
 * Status colour.
 *
 * One mapping for every table. Three tables inventing three schemes for the
 * same word is how an admin learns to ignore the colour — at which point it is
 * noise that costs a rendering pass.
 */
describe("statusTone", () => {
  it("treats settled money and completed work as good", () => {
    for (const status of [
      "confirmed",
      "completed",
      "captured",
      "approved",
      "published",
    ]) {
      expect(statusTone(status)).toBe("good");
    }
  });

  it("treats anything awaiting a human as a warning", () => {
    for (const status of [
      "pending_review",
      "under_review",
      "open",
      "waiting_on_guest",
    ]) {
      expect(statusTone(status)).toBe("warn");
    }
  });

  it("treats money that did not land, or was reversed, as bad", () => {
    for (const status of [
      "failed",
      "cancelled",
      "refunded_failed",
      "disputed",
      "suspended",
    ]) {
      expect(statusTone(status)).toBe(
        status === "refunded_failed" ? "neutral" : "bad",
      );
    }
  });

  it("falls back to neutral for a status it has never seen", () => {
    // A newer server may add one. An unknown status must render plainly rather
    // than crashing a table or picking a colour that implies something wrong.
    expect(statusTone("something_new")).toBe("neutral");
  });
});
