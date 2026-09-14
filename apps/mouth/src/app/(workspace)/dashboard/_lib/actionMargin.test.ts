import { describe, it, expect } from "vitest";
import {
  buildActionMargin,
  mastheadSentence,
  type MarginPractice,
} from "./actionMargin";

/**
 * The ownership law of "Your action margin" (concept-K v2 §3): copper means
 * the signed-in viewer is the NEXT ACTOR, derived from the viewer and the
 * record together — never from a raw status alone, never from a date.
 *
 * Every case below is a GUILT/INNOCENCE pair on one clause of that law, so a
 * regression names which clause broke rather than just "the queue changed".
 */

const practice = (over: Partial<MarginPractice> = {}): MarginPractice => ({
  id: 4187,
  title: "Work Permit Extension",
  client: "Client 0412",
  status: "waiting_documents",
  ...over,
});

describe("the review family exposes only a count", () => {
  it("renders one row carrying the count, not one row per document", () => {
    const { items, count } = buildActionMargin({
      reviewItems: [{}, {}, {}],
      practices: [],
      practicesAreMine: true,
    });
    expect(items).toHaveLength(1);
    expect(items[0].title).toBe("3 documents await review");
    expect(items[0].detail).toBe("Review queue");
    expect(items[0].state).toBe("Your review");
    expect(items[0].href).toBe("/review");
    expect(count).toBe(1);
  });

  it("says 'document awaits' for one and disappears at zero", () => {
    expect(
      buildActionMargin({
        reviewItems: [{}],
        practices: [],
        practicesAreMine: true,
      }).items[0].title,
    ).toBe("1 document awaits review");
    expect(
      buildActionMargin({
        reviewItems: [],
        practices: [],
        practicesAreMine: true,
      }).items,
    ).toEqual([]);
  });

  it("is absent, not zero, while the queue is still in flight", () => {
    expect(
      buildActionMargin({
        reviewItems: undefined,
        practices: [],
        practicesAreMine: true,
      }).items,
    ).toEqual([]);
  });
});

describe("a practice enters the margin only when the viewer is next", () => {
  it("GUILTY of nothing: a blocked practice in the viewer's own list enters", () => {
    const { items } = buildActionMargin({
      reviewItems: [],
      practices: [practice({ daysRemaining: 9 })],
      practicesAreMine: true,
    });
    expect(items).toHaveLength(1);
    expect(items[0].id).toBe("practice-4187");
    expect(items[0].title).toBe("Client 0412 · Work Permit Extension");
    expect(items[0].detail).toBe("Assigned to you");
    expect(items[0].state).toBe("Documents");
    expect(items[0].href).toBe("/process/4187");
  });

  it("accepts the dashboard summary's short code for the same status", () => {
    const { items } = buildActionMargin({
      reviewItems: [],
      practices: [practice({ status: "documents" })],
      practicesAreMine: true,
    });
    expect(items).toHaveLength(1);
  });

  it("INNOCENCE: the same record is excluded when ownership is not derivable", () => {
    // An admin's practice array is the whole book, so `assigned_to` cannot be
    // read off it. Where ownership is not derivable the law says wait, not you.
    const { items } = buildActionMargin({
      reviewItems: [],
      practices: [practice()],
      practicesAreMine: false,
    });
    expect(items).toEqual([]);
  });

  it("INNOCENCE: a status that is not blocked on the assignee stays out", () => {
    for (const status of ["in_progress", "completed", "inquiry", "quotation"]) {
      const { items } = buildActionMargin({
        reviewItems: [],
        practices: [practice({ status })],
        practicesAreMine: true,
      });
      expect(items, status).toEqual([]);
    }
  });
});

describe("a date is urgency and never ownership", () => {
  it("marks a near deadline urgent without changing who is next", () => {
    const near = buildActionMargin({
      reviewItems: [],
      practices: [practice({ daysRemaining: 2 })],
      practicesAreMine: true,
    }).items[0];
    expect(near.urgent).toBe(true);
    expect(near.when).toBe("2d");

    const far = buildActionMargin({
      reviewItems: [],
      practices: [practice({ daysRemaining: 30 })],
      practicesAreMine: true,
    }).items[0];
    expect(far.urgent).toBe(false);
  });

  it("does not let a date pull an unowned record into the margin", () => {
    const { items } = buildActionMargin({
      reviewItems: [],
      practices: [practice({ status: "in_progress", daysRemaining: 0 })],
      practicesAreMine: true,
    });
    expect(items).toEqual([]);
  });
});

describe("the masthead sentence never claims more than the page paints", () => {
  it("counts both clauses", () => {
    expect(mastheadSentence(4, 3)).toBe(
      "4 things are moving; 3 need your action.",
    );
    expect(mastheadSentence(1, 1)).toBe(
      "1 thing is moving; 1 needs your action.",
    );
  });

  it("disappears when it has nothing to report", () => {
    expect(mastheadSentence(0, 0)).toBeUndefined();
  });

  it("stays honest when one clause is empty", () => {
    expect(mastheadSentence(2, 0)).toBe(
      "2 things are moving; nothing needs your action.",
    );
    expect(mastheadSentence(0, 2)).toBe(
      "Nothing is moving; 2 need your action.",
    );
  });
});
