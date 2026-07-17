# Build-runner Gradle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить «зависания» Gradle-сборок через build-runner: дисциплина таймаутов, протокол фоновых сборок, диагностика инфраструктурных сбоев, процедура восстановления демонов.

**Architecture:** Четыре правки маркдаун-конфигурации: агент `build-runner` получает правила исполнения (timeout, одна сборка за раз, протокол «moved to background») и формат INFRASTRUCTURE FAILURE; скилл `build` — последовательную диспетчеризацию и процедуру восстановления демонов (выполняет главная сессия); README — секцию настроек хоста; CHANGELOG — запись. Код не меняется — только инструкции агента/скилла.

**Tech Stack:** Markdown-файлы плагина Claude Code (frontmatter агента, SKILL.md), git.

**Spec:** `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md`

## Execution status (2026-07-17)

Вся файловая работа выполнена и отревьюена (SDD: spec+quality ревью на задачу, ре-ревью после фиксов). Финальное whole-branch ревью (d972c69..3c1ea76): 0 Critical, 0 Important, **Ready to merge — Yes**; гейт мержа — Task 4 Step 3 (смоук-тесты) и пре-PR удаление `docs/superpowers/`. Детали, минорки (все ship-as-is) и вердикты — в леджере `.superpowers/sdd/progress.md`.

## Global Constraints

- Тексты файлов плагина — на английском, в стиле существующих секций. Кириллицы в `agents/`, `skills/`, `README.md`, `CHANGELOG.md` быть не должно.
- Ветка: `build-runner-hardening` (уже создана и активна). Рабочая директория: `/opt/github/zinin/claude-forge`.
- `docs/gradle-build-runner-hardening-report.md` — untracked, НЕ коммитить; остаётся локальным архивом (после мержа можно удалить). `.gitignore` сознательно не трогаем — личный локальный файл не должен попадать в публичный репозиторий. В `git add` передавать только явные пути файлов, никогда `git add docs/`, `git add -A` или `git commit -am`.
- Агенту build-runner добавляются ТОЛЬКО инертные инструменты: read-only диагностика `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)` и пейсинг ожидания `Bash(sleep:*)`. Никакого `kill` в tools агента.
- Каждое сообщение коммита заканчивается трейлером (отдельной строкой после пустой):
  `Claude-Session: <URL текущей сессии-исполнителя — по правилу харнеса; НЕ переиспользовать URL из этого документа>`
  (Резолюция исполнения, одобрена пользователем: у локальной CLI-сессии web-URL нет — пишется её локальный session id; сессия-исполнитель плана использовала `9dced053-ad2b-440b-bbd9-1b7f39c76336`.)
- Метки `INFRASTRUCTURE FAILURE`, `Daemon Recovery Procedure`, `safe to retry` совпадают в обоих файлах дословно. Метка `run daemon recovery procedure first (see build skill)` пишется полностью в отчёте агента; скилл матчит её по префиксу `run daemon recovery procedure first` (хвост «(see build skill)» внутри самого скилла — самоссылка, опускается сознательно). Агенту предписано метки не перефразировать.
- Перед созданием PR (этап finishing, НЕ эти таски): `git rm -r docs/superpowers/` и отдельный коммит — plan/design/review-документы не должны попасть в PR diff (правило пользователя).
- Тестов/сборки в репо нет — верификация каждой правки: `grep` с ожидаемым выводом + вычитка; поведенческие смоук-тесты — до мержа через `claude --plugin-dir` (Task 4).

---

### Task 1: `agents/build-runner.md` — модель, инструменты, правила исполнения, инфра-сбои

✅ Done — see commit: `655f5ef` (spec+quality ревью чистое; все верификационные grep-ы прошли).

---

### Task 2: `skills/build/SKILL.md` — последовательная диспетчеризация, инфра-ретраи, восстановление демонов

✅ Done — see commit: `0cc7627` (spec+quality ревью чистое; кросс-файловый контракт меток с агентом проверен).

---

### Task 3: `README.md` — секция Recommended host setup + актуализация заметки о модели

✅ Done — see commits: `2d1dc69`, `ae1a6d1` (ревью-фикс, одобрен пользователем: в Recovery permissions добавлены `ps` и `Bash(ps:*)`).

---

### Task 4: `CHANGELOG.md` + финальная сверка

**Files:**
- Modify: `CHANGELOG.md`

- [x] **Step 1: Запись в Unreleased** — ✅ Done: `f64f854` + ревью-фикс `3c1ea76` (одобрен пользователем: «explicit 30-minute Bash timeout ask on every build command (dependency installs included; harness-clamped to the host ceiling)» вместо исходного «explicit 10-minute…»).

- [x] **Step 2: Финальная кросс-файловая сверка** — ✅ Done: все grep-ы в ожидаемых значениях (INFRASTRUCTURE FAILURE 7/7 агент/скилл; обе метки Recommended Action в обоих файлах; «see build skill» ↔ `## Daemon Recovery Procedure` резолвится; кириллицы нет; `git status --short` — ровно `?? docs/gradle-build-runner-hardening-report.md`).

- [ ] **Step 3: Смоук-тесты до мержа (вручную, из ветки)**

Запустить тестовую сессию с изменённым плагином (`claude --plugin-dir /opt/github/zinin/claude-forge`) на реальном Gradle-проекте и проверить три сценария:

1. Сборка >2 мин: команда агента идёт с `timeout: 1800000` (кламп к потолку хоста) и `--console=plain`, завершается в форграунде, отчёт корректен.
2. Сборка >10 мин (или искусственно замедленная): уходит в фон; агент поллит `sleep 30` + Grep, НЕ перезапускает сборку, отчитывается фактическим результатом.
3. Негативный кейс: занять глобальный lock вторым Gradle-процессом → агент отдаёт INFRASTRUCTURE FAILURE с верным Owner PID и Recommended Action; скилл выполняет ровно один ретрай (с recovery при живом владельце).

При провале любого сценария — остановиться и обсудить с пользователем до мержа.

Дополнительно в сценарии 3 (рекомендация финального ревью): проверить (a) префикс-матч полной метки агента против короткой в скилле; (b) проходит ли пайп `jps -lv | grep -E '…'` агента через allowlist `Bash(jps:*)` — если режется, менять инструкцию агента на чистый `jps -lv` + фильтрацию Grep-инструментом (согласовать с пользователем).

- [x] **Step 4: Commit** — ✅ Done: `f64f854` (фикс формулировки — отдельным коммитом `3c1ea76`).
