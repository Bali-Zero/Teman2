# Standalone container for @UkrBaliVisaAssistant_bot.
# Brain = `claude` CLI (Fable 5) using your own CLAUDE_CODE_OAUTH_TOKEN.
# Independent of Nuzantara: only needs the bot token, the Google Doc, and your Claude token.
FROM node:22-slim

# python3 for the bot (stdlib only — no pip deps), ca-certificates for TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# the brain: Claude Code CLI (headless `-p`, authed via CLAUDE_CODE_OAUTH_TOKEN env)
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app
COPY ukrbali_bot.py .

# defaults (override in Railway → Variables if needed)
ENV UKRBALI_USE_RAG=0 \
    UKRBALI_CLAUDE_MODEL=claude-fable-5 \
    UKRBALI_KNOWLEDGE_DOC_ID=1HYeR-9znPo9-wujfI79cbpmmHz-ROWT_GwmvykRZ_go

# REQUIRED env (set in Railway → Variables, NOT here):
#   UKRBALI_BOT_TOKEN        — from @BotFather
#   CLAUDE_CODE_OAUTH_TOKEN  — your token from `claude setup-token`

CMD ["python3", "-u", "ukrbali_bot.py"]
