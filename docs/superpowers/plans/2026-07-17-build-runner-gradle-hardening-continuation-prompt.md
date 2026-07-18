# Continuation prompt: build-runner Gradle hardening — finishing (удаление docs/superpowers + PR)

Скопируйте всё ниже разделителя в новую сессию Claude Code, запущенную в `/opt/github/zinin/claude-forge`. **Нужны git remote и `gh`** — у предыдущей сессии их не было, поэтому finishing перенесён сюда.

Этот файл ЗАМЕНЯЕТ предыдущий continuation prompt. Файловая работа, все ревью (SDD, whole-branch, внешнее mesh) и **все три смоук-сценария ЗАВЕРШЕНЫ — PASS**; пост-смоук фиксы закоммичены (`afc9448` — поллинг фоновых сборок; `f92854c` — D4/D5 по итогам сценария 3). Последний содержательный коммит — `f92854c`; поверх него docs-коммит с этим промптом (актуальный HEAD ветки).

---

## TASK

Выполни finishing ветки `build-runner-hardening` (гейт мержа снят): удаление `docs/superpowers/` отдельным коммитом, затем push и PR в master. Ориентир — superpowers:finishing-a-development-branch.

## CRITICAL: DO NOT START WORKING

**СТОП. Прочитай внимательно.** После загрузки контекста ты ОБЯЗАН:
1. Прочитать документы и понять контекст.
2. Кратко изложить понимание.
3. **ЖДАТЬ явной команды пользователя перед ЛЮБЫМИ действиями.**

**НЕЛЬЗЯ:** запускать команды (кроме чтения документов), менять файлы, коммитить, пушить, создавать PR, самому решать что дальше. Пользователь сам скажет.

## DOCUMENTS

- Design: `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md`
- Plan: `docs/superpowers/plans/2026-07-17-build-runner-gradle-hardening.md` (все шаги закрыты; секция «Execution status» — итоговое состояние)
- Ledger: `.superpowers/sdd/progress.md` — ОБЯЗАТЕЛЬНО, особенно секции «Mesh-review pass», «Smoke tests (2026-07-18)» и «Smoke scenario 3 + fixes (2026-07-18)» (форензика всех смоуков, решения по расхождениям D1–D5).

Прочитай документы ДО git-операций: после `git rm -r docs/superpowers/` design/plan/этот промпт исчезнут из рабочей копии (останутся в истории ветки).

## PROGRESS

**Выполнено (закоммичено):**
- [x] Tasks 1–4 целиком, включая Task 4 Step 3: смоук-сценарии 1, 2, 3 — все PASS форензически.
- [x] Whole-branch ревью (Ready to merge — Yes) + внешнее mesh-review (`07f2a20`, `1f291ae`).
- [x] Пост-смоук фиксы: `afc9448` (until-loop поллинг в субагенте), `f92854c` (D4: timeout-подсказка для `--stop` в recovery; D5: вариативность формулировки lock-сигнатуры).

**Осталось (ровно два шага):**
- [ ] `git rm -r docs/superpowers/` и ОТДЕЛЬНЫЙ коммит (правило пользователя: plan/design-доки не должны появиться в diff PR; в истории ветки останутся).
- [ ] Push ветки + PR в master через `gh`. PR body заканчивается ссылкой на сессию по правилу харнеса.

## SESSION CONTEXT

- **Смоук-3 итог:** SIGSTOP-заморозка демона жертвенной сборки frigate → реальная сигнатура `Timeout waiting to lock journal cache (...) Owner PID: 215664` → агент: одна инвокация, предписанный `ps`-триаж (STAT `T` → alive), дословный INFRASTRUCTURE FAILURE с полной меткой → скилл: префикс-матч, recovery по шагам, kill ТОЛЬКО владельца, ровно ОДИН ретрай → BUILD SUCCESSFUL in 3m 19s. 0 `Blocked:` / 0 tool_use_error. Форензика: `~/.claude/projects/-opt-github-zinin-frigate-analyzer/9f9124d5-e2eb-44cf-ba2a-00b99d9666c7*`.
- **D1–D3 — осознанно ship-as-is** (решение пользователя; детали в леджере): D1 — пайп на jstack вопреки инструкции (graceful в строгих сессиях), D2 — внепротокольная read-only диагностика, D3 — импровизация `kill -CONT` (артефакт синтетического T-state). НЕ чинить, НЕ переоткрывать.
- **Ре-тест D4/D5 не проводился** — признан ненужным (аддитивные подсказки на пути, доказанном без них; D5 — только текст примера). Рецепт сценария 3 воспроизводим за ~15 мин (см. леджер), если пользователь захочет.
- **Трейлер коммитов:** «по правилу харнеса» — если у сессии есть web-URL (в системном git-правиле), писать его; локальный session id — только если URL нет. Предыдущая сессия использовала `https://claude.ai/code/session_01Gw2EszCi7JnDjHBimkvdgs`.
- `docs/gradle-build-runner-hardening-report.md` — untracked ЛОКАЛЬНЫЙ архив: НЕ коммитить, НЕ удалять (после мержа пользователь решит сам).
- `.superpowers/sdd/` в .gitignore — в PR не попадает, не трогать.
- Кириллицы в `agents/`, `skills/`, `README.md`, `CHANGELOG.md` нет (проверено грепом); в net-diff PR должны попасть только эти файлы.
- Хост чист: тестовые демоны погашены, фоновых задач прошлой сессии нет.

## PLAN QUALITY WARNING

Finishing прост, но при любой неожиданности (конфликт при push, лишние файлы в diff, вопросы по тексту PR) — ОСТАНОВИСЬ, опиши расхождение, спроси пользователя. Git-гигиена: `git add`/`git rm` только явные пути; никаких `-A`, `-am`, `git add docs/`.

## Прочие правила

- Не переоткрывать закрытые решения: 5 спорных mesh-review, D1–D3 as-is, `model: sonnet`, `timeout: 1800000`, хирургический recovery, метки дословно/по префиксу.
- PR: заголовок и описание — про суть hardening (timeout-дисциплина, протокол фоновых сборок, INFRA-классификация и daemon recovery, model haiku→sonnet, host setup docs); в net-diff PR — только `agents/build-runner.md`, `skills/build/SKILL.md`, `README.md`, `CHANGELOG.md`.

## INSTRUCTIONS

1. Прочитай документы (леджер — обязательно).
2. Пойми прогресс и контекст.
3. Кратко изложи понимание.
4. **СТОП и ЖДИ** — никаких действий.
5. Спроси: «Начинаем finishing — удаление docs/superpowers и PR?»
