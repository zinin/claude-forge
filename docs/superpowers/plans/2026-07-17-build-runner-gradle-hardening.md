# Build-runner Gradle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить «зависания» Gradle-сборок через build-runner: дисциплина таймаутов, протокол фоновых сборок, диагностика инфраструктурных сбоев, процедура восстановления демонов.

**Architecture:** Четыре правки маркдаун-конфигурации: агент `build-runner` получает правила исполнения (timeout, одна сборка за раз, протокол «moved to background») и формат INFRASTRUCTURE FAILURE; скилл `build` — последовательную диспетчеризацию и процедуру восстановления демонов (выполняет главная сессия); README — секцию настроек хоста; CHANGELOG — запись. Код не меняется — только инструкции агента/скилла.

**Tech Stack:** Markdown-файлы плагина Claude Code (frontmatter агента, SKILL.md), git.

**Spec:** `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md`

## Execution status (2026-07-17)

Вся файловая работа выполнена и отревьюена (SDD: spec+quality ревью на задачу, ре-ревью после фиксов). Финальное whole-branch ревью (d972c69..3c1ea76): 0 Critical, 0 Important, **Ready to merge — Yes**. Затем внешнее mesh-review (7 ревьюеров: builtin claude + codex + 5 ext-моделей zai/glm, alibaba/qwen, deepseek/v4-pro, ollama/kimi, ollama/minimax; все 6 врапперов REAL, 0 flip) дало ещё две правки: `07f2a20` (авто-фиксы — Maven `-B` поднят в Execution Rules, честная `ps -o pid,stat,args` вместо `ps -fp`, разведены dead-owner/ps-unavailable, приоритет owner-триажа для registry-lock) и `1f291ae` (5 спорных решений, все одобрены пользователем). HEAD ветки — `1f291ae`. Гейт мержа не изменился: Task 4 Step 3 (смоук-тесты) и пре-PR удаление `docs/superpowers/`. Детали, минорки (все ship-as-is), вердикты ревью и решения по спорным — в леджере `.superpowers/sdd/progress.md`.

**Смоук-прогресс (2026-07-18): все 3 сценария — PASS, гейт мержа по смоукам СНЯТ.** Сценарий 2 вскрыл дефект поллинга (fix **`afc9448`**, повторный прогон чист). Сценарий 3 (негативный lock-кейс; SIGSTOP-заморозка демона фикстурной сборки frigate): поймана реальная сигнатура `Timeout waiting to lock journal cache (...) Owner PID`, агент отдал дословный INFRASTRUCTURE FAILURE с полной меткой и корректным триажем живого владельца, скилл сматчил метку по префиксу, выполнил хирургический recovery (kill только владельца) и ровно ОДИН ретрай → BUILD SUCCESSFUL. Из 5 зафиксированных расхождений D1–D3 — ship-as-is (решение пользователя), D4/D5 исправлены коммитом **`f92854c`** (timeout-подсказка для `--stop` в recovery; вариативность формулировки сигнатуры); ре-тест признан ненужным (аддитивные правки). Форензика и детали — в леджере. Остался finishing: `git rm -r docs/superpowers/` отдельным коммитом + push и PR в master (нужны git remote/gh — следующая сессия).

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

- [x] **Step 3: Смоук-тесты до мержа (вручную, из ветки)** — ✅ Done (2026-07-18): все 3 сценария PASS через `claude --plugin-dir` из каталога тест-проекта. (1) frigate, форграунд ~6 мин: `timeout: 1800000`, `--console=plain`, корректный отчёт. (2) pbx-bill, реальный 10-мин потолок: уход в фон, поллинг until-loop'ом после fix `afc9448`, без перезапуска, точный результат. (3) негативный lock-кейс (SIGSTOP-рецепт): INFRASTRUCTURE FAILURE с верным Owner PID и полной меткой, префикс-матч, хирургический recovery, ровно один ретрай. Подпункт (a) проверен; подпункт (b) снят (mesh-review 5/5 убрал пайпы). Пост-смоук фиксы: `afc9448`, `f92854c`. Форензика — в леджере.

- [x] **Step 4: Commit** — ✅ Done: `f64f854` (фикс формулировки — отдельным коммитом `3c1ea76`).
