# Marketing Skills Bundle

Коллекция из 35 маркетинговых скиллов для Claude Code: SEO, CRO, копирайтинг, paid ads, контент-стратегия, email и многое другое.

## Установка одного скилла

```bash
# Замени <skill-name> на нужный (например: paid-ads, page-cro, seo-audit)
SKILL=paid-ads
mkdir -p ~/.claude/skills && \
curl -sSL "https://github.com/yasikvlad/marketing-skills/archive/refs/heads/main.tar.gz" \
  | tar -xz --strip-components=2 -C ~/.claude/skills "marketing-skills-main/skills/$SKILL"
```

## Установка всех скиллов сразу

```bash
git clone https://github.com/yasikvlad/marketing-skills /tmp/marketing-skills && \
cp -r /tmp/marketing-skills/skills/* ~/.claude/skills/ && \
rm -rf /tmp/marketing-skills
```

## Список скиллов

| Категория | Скилл |
|-----------|-------|
| **Копирайтинг** | `copywriting`, `copy-editing`, `cold-email` |
| **CRO** | `page-cro`, `form-cro`, `popup-cro`, `onboarding-cro`, `signup-flow-cro`, `paywall-upgrade-cro`, `ab-test-setup`, `churn-prevention`, `analytics-tracking` |
| **SEO** | `seo-audit`, `ai-seo`, `programmatic-seo`, `schema-markup`, `site-architecture`, `competitor-alternatives` |
| **Контент** | `social-content`, `content-strategy`, `lead-magnets` |
| **Реклама** | `paid-ads`, `ad-creative`, `creative-ads` |
| **Стратегия** | `marketing-ideas`, `marketing-psychology`, `pricing-strategy`, `free-tool-strategy`, `referral-program`, `revops`, `launch-strategy`, `product-marketing-context` |
| **Воронки** | `email-sequence`, `sales-enablement` |
| **Дизайн** | `superdesign` |
| **Утилиты** | `notebooklm` |

## После установки

Перезапусти Claude Code — скиллы автоматически подцепятся из `~/.claude/skills/`.
