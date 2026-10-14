---
name: tone-of-voice-analyzer
version: 1.0.0
description: |
  Обратный инжиниринг Tone of Voice из любого текста. Научно обоснованный 8-уровневый анализ.
  Создает готовый ToV-документ: voice-атрибуты, шкалы, лексический код, Do/Don't, адаптация по контекстам.
  Работает с транскриптами речи, постами, статьями, продающими текстами.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# Tone of Voice — скилл-указатель

Источник: https://github.com/yasikvlad/tone-of-voice (Vlad Yasko), вендорен байт-в-байт в
`vendor/yasikvlad/tone-of-voice/` (провенанс — `vendor/yasikvlad/UPSTREAM.md`).

## Как выполнять

1. Прочитай `vendor/yasikvlad/tone-of-voice/SKILL.md` и следуй ему как основной инструкции.
2. Входные данные — транскрипты, посты, статьи или продающие тексты, которые даёт пользователь.
3. Результат (ToV-документ) сохраняй в рабочий каталог пользователя.
4. Отвечай на языке пользователя.
