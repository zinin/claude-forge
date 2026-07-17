# Review Iteration 1 — 2026-07-17 16:24

## Источник

- Design: `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md`
- Plan: `docs/superpowers/plans/2026-07-17-build-runner-gradle-hardening.md`
- Review agents: claude (built-in, fresh context), codex (gpt-5.6-sol, reasoning max), ext-claude alibaba/qwen (Qwen 3.7 Plus), ext-claude deepseek/v4-pro (DeepSeek V4 Pro 1M), ext-claude ollama/minimax (MiniMax M3). Сбои: zai/glm и ollama/kimi (CLI умирал на середине, оригинал + 1 ретрай; отчёты недоступны).
- Merged output: `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-review-merged-iter-1.md`
- Доп. проверка фактов: claude-code-guide (доки) + эмпирические тесты в сессии (кламп timeout, env хоста).

## Замечания

### [CRITICAL-1] Битый old_string в Task 2 Step 1 — терялся «/type-check»

> В фактическом SKILL.md:53 правило «Do not run ANY build/test/lint/type-check command…», в плане (old и new) — усечённое «build/test/lint».

**Источник:** claude C1, deepseek C1 (подтверждено проверкой файла)
**Статус:** Автоисправлено
**Действие:** `/type-check` восстановлен в обеих строках плана.

### [CRITICAL-2] Протокол ожидания фоновой сборки неисполним (нет механизма/каденции/предела)

> Субагент не может «просто ждать»; Read целого лога раздувает контекст; при реальном зависании агент поллит вечно.

**Источник:** claude C2+S1+Q3, codex C1+Q1, qwen C3+S16, deepseek C2, minimax N1+S2
**Статус:** Автоисправлено
**Действие:** `Bash(sleep:*)` в tools; цикл `sleep 30` → Grep файла вывода по маркерам (уведомление — бонус, не механизм; подтверждено guide: доставка в следующем ходу, v2.1.211+); Read только хвоста; бюджет ожидания (~20 мин / вывод не растёт ~10 мин) → INFRASTRUCTURE FAILURE `orphaned background build` + Recommended Action recovery; ветка обработки в скилле.

### [CRITICAL-3] Инструкционный тупик: recovery требует ./gradlew --stop, запрещённый скиллом

**Источник:** claude C3
**Статус:** Автоисправлено
**Действие:** Оговорка в Daemon Recovery Procedure: команды процедуры — не build/test/lint, выполняются главной сессией напрямую, build-runner-у не делегируются.

### [CRITICAL-4] (+ QUESTION-1) README противоречит явному timeout агента; стратегия таймаутов

> BASH_DEFAULT не влияет на сборки агента; BASH_MAX никем не запрашивается; сборки >10 мин всегда фоновые.

**Источник:** claude Cn4+Q1, codex C4+S4, qwen C1, deepseek C3+Q1+Q3, minimax S4+Q7 (5/5 ревьюеров)
**Статус:** Обсуждено с пользователем
**Ответ:** Вариант A — агент передаёт `timeout: 1800000`; харнес молча клампит к потолку (эмпирически проверено в сессии: 1800000 и 3600000 приняты без ошибки на хосте без BASH_*_TIMEOUT_MS; отклонения нет). README переписан честно: BASH_MAX — форграунд для длинных сборок, BASH_DEFAULT — страховка команд без явного timeout.
**Действие:** Execution Rule 1, README-пункт, смоук-кейс, решение в «Принятых решениях» дизайна.

### [CRITICAL-5] Daemon Recovery мог убить чужие здоровые демоны

> blanket-kill всех GradleDaemon/KotlinCompileDaemon бьёт по IDE и параллельным сессиям; Owner PID из отчёта не использовался.

**Источник:** codex C2+S2+Q2, deepseek Cn4, minimax N10, qwen S18
**Статус:** Обсуждено с пользователем
**Ответ:** Вариант A — хирургический recovery: kill только подтверждённого владельца (identity-проверка `ps -fp` против PID reuse); чужой процесс → спросить пользователя; нет PID в отчёте → только `--stop` + пауза; одна повторная проверка при новом владельце, дальше не циклиться.
**Действие:** Процедура переписана в плане и дизайне; критерии приёмки и CHANGELOG-текст обновлены.

### [CRITICAL-6] Классификация INFRA vs BUILD FAILED: одна сигнатура

**Источник:** claude Cn6, qwen C5+S15, deepseek Cn6, codex C5
**Статус:** Автоисправлено
**Действие:** Добавлены сигнатуры daemon disappeared / could not connect / stopped to free memory / ERROR-registry-lock → `safe to retry`; правило «if unsure → BUILD FAILED»; список false friends.

### [CRITICAL-7] --console=plain не достигал главного пути (Step 0)

**Источник:** claude Cn7, codex Cn1, qwen C4, deepseek Cn7, minimax C2 (5/5)
**Статус:** Автоисправлено
**Действие:** Правило поднято в Execution Rules (все `./gradlew`, включая точные команды вызывающего, с оговоркой про уже переданный `--console`); интро-строка «including exact commands passed by the caller in Step 0»; примеры Step 0 обновлены; Maven получил симметричный `-B`.

### [CRITICAL-8] Контракт меток нарушен планом; Output format скилла не обновлён

**Источник:** codex C3, claude Cn10+S2, deepseek Cn9, qwen Cn14+Q3, minimax N2+N6
**Статус:** Автоисправлено
**Действие:** Семантика зафиксирована явно (полная метка в отчёте агента, префикс-матч в скилле — сознательно); «use verbatim — do not paraphrase» в формате агента; INFRASTRUCTURE FAILURE добавлен в Output format скилла; все 4 метки грепаются в верификации обоих файлов.

### [CRITICAL-9] (+ QUESTION-3) Контракт INFRASTRUCTURE FAILURE неполон

**Источник:** codex C5+Q3, claude Cn5+S3, deepseek Cn6, minimax S3+S6+Q3+Q4, qwen Q1
**Статус:** Автоисправлено
**Действие:** `orphaned background build` связан с бюджетом ожидания (производится правилом 3); ветки: dead/zombie → safe to retry, PID неизвестен/ps недоступен → BUILD FAILED (закрывает и вопрос о других форматах lock-сообщений); поле «Background Task ID (if applicable)»; jps-снимок в Details; в скилле — malformed → BUILD FAILED.

### [CONCERN-1] Механика ожиданий/пауз главной сессии

**Источник:** claude Cn8, deepseek Cn5, qwen Cn6, minimax Q10
**Статус:** Автоисправлено
**Действие:** Паузы командами (`sleep 15`/`sleep 20`); «ждать неведомым способом» заменено маршрутизацией (возврат при живой сборке → следующий сбой = infra с живым владельцем); зависание самого build-runner — в Limitations.

### [CONCERN-2] JDK-утилиты: PATH, permission-паттерны, применение jstack

**Источник:** qwen C2+Cn8+Q6, minimax N5+N7+Q2, codex Cn3, claude Cn9, deepseek
**Статус:** Автоисправлено
**Действие:** Вызовы по PATH (префикс-матч `Bash(jps:*)` подтверждён guide — абсолютные пути не матчатся); фиксированная команда `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'`; применение jstack прописано (`| head -200`, выжимка в Details при живом владельце); fallback «не на PATH → пропустить, отметить в Details»; README-строка про JDK bin на PATH.

### [CONCERN-3] Бюджет попыток при смешанных сценариях

**Источник:** claude Cn11, codex Cn5, deepseek Cn10+Q4, minimax C6
**Статус:** Автоисправлено
**Действие:** «Максимум 4 запуска за вызов скилла: до 3 попыток на ошибках кода + не более 1 инфра-ретрая; авто-фиксы не считаются».

### [CONCERN-4] Хрупкая верификация; смоук после мержа

**Источник:** codex C6+S5, minimax C3+Q5+Q6+S10+S13, claude S7, qwen S20+Q9, deepseek Cn8
**Статус:** Автоисправлено
**Действие:** Пер-команда greps (`./gradlew` без console=plain, `mvn` без -B — перечисление нарушителей), метки в обоих файлах, frontmatter-scoped kill-проверка, regression-grep (BUILD SUCCESSFUL/MIXED PROJECT), проверка кириллицы, git status; смоук-тесты перенесены ДО мержа (`claude --plugin-dir`, 3 сценария включая негативный lock-кейс).

### [CONCERN-5] Сериализация не глобальна; запросы «в полёте»

**Источник:** codex Cn2, qwen Cn10, minimax N3
**Статус:** Автоисправлено
**Действие:** Limitations: «защита только от самодублирования»; правило «уточнение во время работы агента → дождаться отчёта, затем новый диспатч».

### [CONCERN-6] Риски README-рекомендаций (auto-detect, idletimeout, merge)

**Источник:** codex Cn4, claude S5, qwen Q5+S19
**Статус:** Автоисправлено
**Действие:** Оговорки: пути подставить свои / не включать при зависимости от автодетекта; трейдофф idletimeout (холодный старт); «add or change the line»; merge settings.json.

### [CONCERN-7] Permissions главной сессии для recovery

**Источник:** qwen Cn9, minimax C5+S9+Q1
**Статус:** Автоисправлено
**Действие:** README-пункт «Recovery permissions» (`Bash(jps:*)`, `Bash(kill:*)`, `Bash(jstack:*)`); отмечена идемпотентность процедуры (безопасно начать заново).

### [CONCERN-8] Ручной триггер recovery (уже осиротевшие/убитые вручную сборки)

**Источник:** minimax C1+Q8
**Статус:** Автоисправлено
**Действие:** Ветка в Step 2 скилла: «пользователь сообщает о зависшей сборке → выполнить процедуру напрямую»; runbook «Quick diagnostics» в README.

### [CONCERN-9] Статус --console=plain: «опционально» в отчёте vs «обязательно» в дизайне

**Источник:** minimax C4+N4, qwen Q4
**Статус:** Автоисправлено
**Действие:** Обоснование зафиксировано в «Принятых решениях»: сверх подтверждённых фактов, но безвреден и стабилизирует парсинг; применяется ко всем Gradle-командам единообразно (включая *Format).

### [CONCERN-10] Трункация вывода не обработана

**Источник:** minimax N12+S8
**Статус:** Автоисправлено
**Действие:** Execution Rule 7 (причину искать в файле через Grep/Read); `jstack … | head -200` в примерах.

### [CONCERN-11] Портируемость и границы поддержки

**Источник:** qwen Cn7+Q2+Q7, codex Cn6+Q4
**Статус:** Автоисправлено
**Действие:** README: Unix-like, Claude Code ≥ 2.1.211; recovery: нет wrapper → пропустить `--stop`; Limitations: watch/долгоживущие команды не диспетчеризуются; ps-fallback в ветках агента.

### [SUGGESTION-1] Симметрия для не-Gradle стеков

**Источник:** deepseek, claude S4+Q5
**Статус:** Автоисправлено
**Действие:** Timeout-правило покрывает dependency installs; `-B` для Maven; «for other stacks report as BUILD FAILED».

### [SUGGESTION-2] README: runbook, no-daemon, стоимость sonnet

**Источник:** minimax S1+S7+S11+S12, qwen Cn12, deepseek
**Статус:** Автоисправлено (частично)
**Действие:** Runbook «Quick diagnostics», строка «never pass --no-daemon», стоимость sonnet в заметке о модели. Ссылка на хеш коммита с rationale НЕ добавлена (хрупко: хеш меняется при rebase/squash).

### [SUGGESTION-3] Процессные шаги плана

**Источник:** claude S6, deepseek, qwen Cn11+Q8+S17
**Статус:** Автоисправлено (частично)
**Действие:** Плейсхолдер `<URL текущей сессии-исполнителя>` во всех трейлерах; напоминание «git rm -r docs/superpowers/ перед PR»; судьба отчёта (локальный архив, удалить после мержа). `.gitignore` НЕ добавлен (личный файл автора не должен попадать в публичный репозиторий; защита — явные пути в git add, запрет -am). Task 1 не дробится (Edit-шаги атомарны).

### [SUGGESTION-4] Архитектурные усиления (state machine, машинные коды, lock-wrapper)

**Источник:** codex S1+S3+S6
**Статус:** Автоисправлено (отложено осознанно)
**Действие:** Зафиксированы в «Вне скоупа» дизайна как будущие направления; текущая итерация — minimally invasive markdown.

### [SUGGESTION-5] Обоснование глобального sonnet

**Источник:** minimax S14, qwen Q10
**Статус:** Автоисправлено
**Действие:** Строка в «Принятых решениях» (протокол одинаков для всех стеков; ветвление модели по стеку не выражается frontmatter'ом); «for all stacks» в README-заметке.

### [SUGGESTION-6] Уточнения recovery

**Источник:** deepseek, qwen S18, minimax Q4
**Статус:** Автоисправлено
**Действие:** jps-снимок «до»; «медленный ≠ зависший» после холодного старта; zombie → safe to retry; новый PID для jstack через jps.

### [QUESTION-2] Семантика жизненного цикла фоновой задачи субагента

**Источник:** claude Q2+Q4, deepseek Q2, minimax Q9, codex Q1
**Статус:** Автоисправлено (проверено фактами)
**Ответ:** Guide: уведомление о завершении доставляется субагенту в следующем ходу (v2.1.211+, 85%); судьба процесса при завершении субагента — пробел в доках. Протокол сформулирован консервативно: полл — механизм, уведомление — бонус; ранний возврат всегда оформляется как orphaned + recovery-этикет — корректно при любом ответе на недокументированную часть.

### [QUESTION-3] Другие форматы lock-сообщений Gradle

**Источник:** qwen Q1
**Статус:** Автоисправлено (влито в CRITICAL-9)
**Действие:** Ветка «PID неизвестен → обычный BUILD FAILED с логами» покрывает любые вариации формата.

## Изменения в документах

| Файл | Изменение |
|------|-----------|
| `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md` | Принятые решения (+5: timeout-стратегия, хирургический recovery, sleep, console=plain, sonnet-все-стеки, PATH-утилиты); Execution Rules 1–7 (полл-цикл, бюджет, timeout 1800000); Infrastructure Failures (сигнатуры, ветки, false friends); формат отчёта (+Background Task ID, verbatim-метки); Изменение 2 (маршрутизация, malformed, ручной триггер, хирургическая процедура, Output format, Limitations); Изменение 3 (5 новых пунктов README); Вне скоупа (+2); критерии приёмки и Проверка переписаны (смоук до мержа). |
| `docs/superpowers/plans/2026-07-17-build-runner-gradle-hardening.md` | Global Constraints (метки, трейлер-плейсхолдер, git rm, кириллица); Task 1: tools (+sleep), Execution Rules, примеры Step 0, Maven -B, Infrastructure Failures, формат, guideline 13, усиленная верификация; Task 2: /type-check-якорь, dispatch discipline, обработчик (+malformed, ручной триггер), хирургическая recovery, Limitations, Output format, верификация; Task 3: README-блок (+4 пункта), заметка о модели, верификация; Task 4: CHANGELOG-текст, финальная сверка, смоук-шаг (новый Step 3). |

## Статистика

- Всего замечаний: 29
- Автоисправлено (без обсуждения): 26
- Авто-применено после анализа: 0
- Обсуждено с пользователем: 3 (CRITICAL-4 + QUESTION-1 — один вопрос; CRITICAL-5)
- Отклонено: 0
- Повторов (автоответ): 0
- Пользователь сказал «стоп»: Нет
- Агенты: claude, codex (gpt-5.6-sol), alibaba/qwen, deepseek/v4-pro, ollama/minimax; сбои — zai/glm, ollama/kimi
