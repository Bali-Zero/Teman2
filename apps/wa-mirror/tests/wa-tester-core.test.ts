// wa-tester-core.test.ts — unit tests for the pure logic behind wa-tester.
//
// No live WhatsApp calls here — everything under test is a pure function or
// a pure state machine driven by injected timestamps. Live-socket glue
// (scripts/wa-tester.ts) is exercised manually against the real bot, not in
// CI.

import { describe, expect, it } from "vitest";

import {
  BOT_JID,
  BOT_PHONE_E164,
  ReplyCollector,
  buildQuestionResult,
  buildTranscript,
  checkRecipientAllowlist,
  extractMessageText,
  isBotReplyJid,
  isPairedFromCreds,
  matchesBotRecipient,
  parseMessageTimestampMs,
  shouldReconnect,
  transcriptHasZeroReplyQuestion,
  validateBattery,
} from "../scripts/wa-tester-core.js";

describe("matchesBotRecipient — allowlist entity matching", () => {
  it("matches the bot's E.164 form", () => {
    expect(matchesBotRecipient("+628213465159")).toBe(true);
  });

  it("matches bare digits (no +)", () => {
    expect(matchesBotRecipient("628213465159")).toBe(true);
  });

  it("matches the local 0-prefixed Indonesian form", () => {
    expect(matchesBotRecipient("08213465159")).toBe(true);
  });

  it("matches a full Baileys JID string", () => {
    expect(matchesBotRecipient("628213465159@s.whatsapp.net")).toBe(true);
  });

  it("does NOT match a different Indonesian number (fails closed)", () => {
    expect(matchesBotRecipient("+6281234567890")).toBe(false);
  });

  it("does NOT match garbage input", () => {
    expect(matchesBotRecipient("not-a-phone")).toBe(false);
    expect(matchesBotRecipient("")).toBe(false);
  });
});

describe("checkRecipientAllowlist — guilt + innocence", () => {
  it("[innocence] passes an object with no recipient-lookalike fields", () => {
    const result = checkRecipientAllowlist({ id: "q1", text: "hello" }, "ctx");
    expect(result.ok).toBe(true);
  });

  it("[innocence] passes when the recipient field matches the bot, any format", () => {
    for (const val of [
      "+628213465159",
      "628213465159",
      "628213465159@s.whatsapp.net",
    ]) {
      const result = checkRecipientAllowlist({ to: val }, "ctx");
      expect(result.ok).toBe(true);
    }
  });

  it("[guilt] refuses when 'to' points at a different number", () => {
    const result = checkRecipientAllowlist(
      { to: "+6281234567890" },
      "battery.questions[0]",
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("battery.questions[0]");
      expect(result.error).toContain(BOT_PHONE_E164);
    }
  });

  it("[guilt] refuses on ANY of the recipient-lookalike keys, not just 'to'", () => {
    for (const key of [
      "recipient",
      "jid",
      "phone",
      "number",
      "target",
      "send_to",
    ]) {
      const result = checkRecipientAllowlist({ [key]: "+15551234567" }, "ctx");
      expect(result.ok).toBe(false);
    }
  });

  it("[innocence] ignores unrelated keys entirely", () => {
    const result = checkRecipientAllowlist(
      { id: "q1", text: "what about my KITAS", note: "+6281234567890" },
      "ctx",
    );
    expect(result.ok).toBe(true);
  });
});

describe("validateBattery", () => {
  const validRaw = {
    questions: [
      { id: "q1", text: "Ciao, come funziona il B211A?" },
      { id: "q2", text: "Quanto costa il KITAS investor?" },
    ],
    reply_timeout_s: 90,
    inter_question_delay_s: 20,
  };

  it("[innocence] accepts a well-formed battery", () => {
    const result = validateBattery(validRaw);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.battery.questions).toHaveLength(2);
      expect(result.battery.reply_timeout_s).toBe(90);
      expect(result.battery.inter_question_delay_s).toBe(20);
    }
  });

  it("[innocence] defaults reply_timeout_s / inter_question_delay_s when omitted", () => {
    const result = validateBattery({ questions: [{ id: "q1", text: "hi" }] });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.battery.reply_timeout_s).toBe(90);
      expect(result.battery.inter_question_delay_s).toBe(20);
    }
  });

  it("[guilt] the ALLOWLIST GUARD refuses a battery whose question targets another number", () => {
    const evil = {
      questions: [
        { id: "q1", text: "hi", to: "+6281234567890" },
        { id: "q2", text: "hi again" },
      ],
    };
    const result = validateBattery(evil);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("battery.questions[0]");
    }
  });

  it("[guilt] the ALLOWLIST GUARD also checks the battery root, not just questions", () => {
    const evil = {
      recipient: "+6281234567890",
      questions: [{ id: "q1", text: "hi" }],
    };
    const result = validateBattery(evil);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("battery:");
    }
  });

  it("rejects a non-object root", () => {
    expect(validateBattery("not an object").ok).toBe(false);
    expect(validateBattery(null).ok).toBe(false);
    expect(validateBattery([1, 2, 3]).ok).toBe(false);
  });

  it("rejects an empty or missing questions array", () => {
    expect(validateBattery({ questions: [] }).ok).toBe(false);
    expect(validateBattery({}).ok).toBe(false);
  });

  it("rejects a question missing id or text", () => {
    expect(validateBattery({ questions: [{ text: "hi" }] }).ok).toBe(false);
    expect(validateBattery({ questions: [{ id: "q1" }] }).ok).toBe(false);
  });

  it("rejects duplicate question ids", () => {
    const result = validateBattery({
      questions: [
        { id: "q1", text: "hi" },
        { id: "q1", text: "hi again" },
      ],
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("duplicate id");
  });

  it("falls back to defaults for non-positive/garbage timeout values", () => {
    const result = validateBattery({
      questions: [{ id: "q1", text: "hi" }],
      reply_timeout_s: -5,
      inter_question_delay_s: "not a number",
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.battery.reply_timeout_s).toBe(90);
      expect(result.battery.inter_question_delay_s).toBe(20);
    }
  });
});

describe("ReplyCollector — quiet-period state machine", () => {
  const SENT_AT = 1_000_000;

  it("keeps collecting before any reply and before the hard timeout", () => {
    const c = new ReplyCollector({
      sentAtMs: SENT_AT,
      replyTimeoutS: 90,
      quietPeriodS: 10,
    });
    expect(c.verdict(SENT_AT + 5_000)).toBe("collecting");
  });

  it("stops on hard timeout with ZERO replies", () => {
    const c = new ReplyCollector({
      sentAtMs: SENT_AT,
      replyTimeoutS: 90,
      quietPeriodS: 10,
    });
    expect(c.verdict(SENT_AT + 90_000)).toBe("stop_timeout");
    expect(c.count).toBe(0);
  });

  it("keeps collecting immediately after one reply (quiet window not yet elapsed)", () => {
    const c = new ReplyCollector({
      sentAtMs: SENT_AT,
      replyTimeoutS: 90,
      quietPeriodS: 10,
    });
    c.addReply("hello", SENT_AT + 3_000);
    expect(c.verdict(SENT_AT + 5_000)).toBe("collecting");
  });

  it("stops on quiet-period completion (10s no new messages after >=1 reply)", () => {
    const c = new ReplyCollector({
      sentAtMs: SENT_AT,
      replyTimeoutS: 90,
      quietPeriodS: 10,
    });
    c.addReply("hello", SENT_AT + 3_000);
    expect(c.verdict(SENT_AT + 3_000 + 10_000)).toBe("stop_quiet");
  });

  it("resets the quiet window on each new reply", () => {
    const c = new ReplyCollector({
      sentAtMs: SENT_AT,
      replyTimeoutS: 90,
      quietPeriodS: 10,
    });
    c.addReply("part 1", SENT_AT + 3_000);
    // 9s after first reply — still inside quiet window, would NOT have
    // stopped yet.
    expect(c.verdict(SENT_AT + 12_000)).toBe("collecting");
    c.addReply("part 2", SENT_AT + 12_000);
    // Another 9s after the SECOND reply — still collecting because the
    // window reset.
    expect(c.verdict(SENT_AT + 21_000)).toBe("collecting");
    // 10s after the second reply — quiet period complete.
    expect(c.verdict(SENT_AT + 22_000)).toBe("stop_quiet");
  });

  it("the hard timeout is a safety cap even mid-conversation (never waits past it)", () => {
    const c = new ReplyCollector({
      sentAtMs: SENT_AT,
      replyTimeoutS: 30,
      quietPeriodS: 10,
    });
    c.addReply("hello", SENT_AT + 25_000); // reply arrives late, quiet window would extend past 30s
    expect(c.verdict(SENT_AT + 30_000)).toBe("stop_timeout");
  });

  it("all() returns a defensive copy", () => {
    const c = new ReplyCollector({ sentAtMs: SENT_AT, replyTimeoutS: 90 });
    c.addReply("hello", SENT_AT + 1_000);
    const snapshot = c.all;
    snapshot.push({ text: "injected", timestampMs: 0 });
    expect(c.count).toBe(1);
  });
});

describe("shouldReconnect — bounded reconnect gate", () => {
  it("never reconnects on a terminal close", () => {
    expect(
      shouldReconnect({ terminal: true, attempt: 1, maxAttempts: 2 }),
    ).toBe(false);
  });

  it("reconnects when attempts remain and the close is non-terminal", () => {
    expect(
      shouldReconnect({ terminal: false, attempt: 1, maxAttempts: 2 }),
    ).toBe(true);
  });

  it("stops once the attempt budget is exhausted (the '515: reconnect once' contract)", () => {
    expect(
      shouldReconnect({ terminal: false, attempt: 2, maxAttempts: 2 }),
    ).toBe(false);
  });
});

describe("extractMessageText", () => {
  it("extracts plain conversation text", () => {
    expect(extractMessageText({ conversation: "hello world" })).toBe(
      "hello world",
    );
  });

  it("extracts extendedTextMessage text (quoted/linked replies)", () => {
    expect(
      extractMessageText({ extendedTextMessage: { text: "quoted reply" } }),
    ).toBe("quoted reply");
  });

  it("prefers conversation over extendedTextMessage when both present", () => {
    expect(
      extractMessageText({
        conversation: "plain",
        extendedTextMessage: { text: "extended" },
      }),
    ).toBe("plain");
  });

  it("returns empty string for media-only / unsupported message shapes", () => {
    expect(extractMessageText({})).toBe("");
    expect(extractMessageText(null)).toBe("");
    expect(extractMessageText(undefined)).toBe("");
    expect(extractMessageText({ imageMessage: { caption: "a photo" } })).toBe(
      "",
    );
  });
});

describe("parseMessageTimestampMs", () => {
  it("converts a numeric Baileys timestamp (seconds) to epoch ms", () => {
    expect(parseMessageTimestampMs(1_700_000_000)).toBe(1_700_000_000_000);
  });

  it("converts a numeric string", () => {
    expect(parseMessageTimestampMs("1700000000")).toBe(1_700_000_000_000);
  });

  it("converts a Long-like object via toNumber()", () => {
    expect(parseMessageTimestampMs({ toNumber: () => 1_700_000_000 })).toBe(
      1_700_000_000_000,
    );
  });

  it("falls back to now() for null/undefined/non-numeric string (never throws/NaN)", () => {
    const before = Date.now();
    expect(Number.isFinite(parseMessageTimestampMs(null))).toBe(true);
    expect(Number.isFinite(parseMessageTimestampMs(undefined))).toBe(true);
    expect(Number.isFinite(parseMessageTimestampMs("not-a-number"))).toBe(true);
    const after = Date.now();
    const val = parseMessageTimestampMs(null);
    expect(val).toBeGreaterThanOrEqual(before);
    expect(val).toBeLessThanOrEqual(after + 1);
  });
});

describe("buildQuestionResult / buildTranscript — transcript assembly", () => {
  const SENT_AT = 1_700_000_000_000;

  it("computes per-reply latency_ms and first_reply_latency_ms", () => {
    const result = buildQuestionResult({ id: "q1", text: "hello" }, SENT_AT, [
      { text: "part 1", timestampMs: SENT_AT + 1_200 },
      { text: "part 2", timestampMs: SENT_AT + 3_400 },
    ]);
    expect(result.reply_count).toBe(2);
    expect(result.replies[0].latency_ms).toBe(1_200);
    expect(result.replies[1].latency_ms).toBe(3_400);
    expect(result.first_reply_latency_ms).toBe(1_200);
    expect(result.sent_at).toBe(new Date(SENT_AT).toISOString());
  });

  it("reports null first_reply_latency_ms and 0 reply_count for a silent question", () => {
    const result = buildQuestionResult(
      { id: "q1", text: "hello" },
      SENT_AT,
      [],
    );
    expect(result.reply_count).toBe(0);
    expect(result.first_reply_latency_ms).toBeNull();
    expect(result.replies).toEqual([]);
  });

  it("buildTranscript aggregates questions_with_zero_replies in the summary", () => {
    const answered = buildQuestionResult({ id: "q1", text: "a" }, SENT_AT, [
      { text: "reply", timestampMs: SENT_AT + 500 },
    ]);
    const silent = buildQuestionResult({ id: "q2", text: "b" }, SENT_AT, []);
    const transcript = buildTranscript({
      batteryFile: "/tmp/battery.json",
      botJid: BOT_JID,
      startedAtMs: SENT_AT,
      finishedAtMs: SENT_AT + 60_000,
      results: [answered, silent],
    });
    expect(transcript.summary.total_questions).toBe(2);
    expect(transcript.summary.questions_with_zero_replies).toBe(1);
    expect(transcript.bot_jid).toBe(BOT_JID);
  });

  it("transcriptHasZeroReplyQuestion flags a battery with any silent question", () => {
    const answered = buildQuestionResult({ id: "q1", text: "a" }, SENT_AT, [
      { text: "reply", timestampMs: SENT_AT + 500 },
    ]);
    const allAnswered = buildTranscript({
      batteryFile: "/tmp/b.json",
      botJid: BOT_JID,
      startedAtMs: SENT_AT,
      finishedAtMs: SENT_AT + 1_000,
      results: [answered],
    });
    expect(transcriptHasZeroReplyQuestion(allAnswered)).toBe(false);

    const silent = buildQuestionResult({ id: "q2", text: "b" }, SENT_AT, []);
    const oneSilent = buildTranscript({
      batteryFile: "/tmp/b.json",
      botJid: BOT_JID,
      startedAtMs: SENT_AT,
      finishedAtMs: SENT_AT + 1_000,
      results: [answered, silent],
    });
    expect(transcriptHasZeroReplyQuestion(oneSilent)).toBe(true);
  });
});

describe("isPairedFromCreds — guilt + innocence (QR-companion vs pairing-code flow)", () => {
  it("[guilt] neither registered nor me.id present → NOT paired", () => {
    expect(isPairedFromCreds({})).toBe(false);
    expect(isPairedFromCreds({ registered: false })).toBe(false);
  });

  it("[innocence-1] pairing-code flow: registered:true → paired", () => {
    expect(isPairedFromCreds({ registered: true })).toBe(true);
  });

  it("[innocence-2] QR-companion flow: registered:false + me.id present → paired", () => {
    expect(
      isPairedFromCreds({
        registered: false,
        me: { id: "628213465159:1@s.whatsapp.net" },
      }),
    ).toBe(true);
  });
});

describe("isBotReplyJid — guilt + innocence (scar #3 UNDER-match, WhatsApp LID rollout)", () => {
  it("[guilt] bot's own phone-JID form matches (pre-existing behaviour, preserved)", () => {
    expect(isBotReplyJid(BOT_JID, null)).toBe(true);
  });

  it("[guilt] bot's phone-JID with a multi-device :N suffix still matches", () => {
    expect(isBotReplyJid("628213465159:5@s.whatsapp.net", null)).toBe(true);
  });

  it("[guilt] a @lid JID that resolves to the bot's phone matches (the actual bug this fixes)", () => {
    expect(isBotReplyJid("224112131756075@lid", "+628213465159")).toBe(true);
  });

  it("[guilt] @lid resolution may come back as bare digits, not just E.164", () => {
    expect(isBotReplyJid("224112131756075@lid", "628213465159")).toBe(true);
  });

  it("[innocence-1] a @lid JID that resolves to a DIFFERENT phone must NOT match", () => {
    expect(isBotReplyJid("224112131756075@lid", "+6281234567890")).toBe(false);
  });

  it("[innocence-2] a @lid JID that fails to resolve (null) must NOT match — fail closed", () => {
    expect(isBotReplyJid("224112131756075@lid", null)).toBe(false);
  });

  it("[innocence-3] some other contact's phone-JID must NOT match", () => {
    expect(isBotReplyJid("6281234567890@s.whatsapp.net", null)).toBe(false);
  });

  it("[innocence-4] a resolved LID phone must NOT rescue an unrelated remoteJid", () => {
    // resolvedLidPhoneE164 is only consulted when remoteJid itself is a LID —
    // it must never leak into matching a phone-JID it wasn't resolved from.
    expect(isBotReplyJid("6281234567890@s.whatsapp.net", "+628213465159")).toBe(
      false,
    );
  });

  it("[innocence-5] group/broadcast/empty JIDs never match", () => {
    expect(isBotReplyJid("123456-789@g.us", "+628213465159")).toBe(false);
    expect(isBotReplyJid("status@broadcast", "+628213465159")).toBe(false);
    expect(isBotReplyJid(null, "+628213465159")).toBe(false);
    expect(isBotReplyJid(undefined, "+628213465159")).toBe(false);
    expect(isBotReplyJid("", "+628213465159")).toBe(false);
  });
});
