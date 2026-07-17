# Дизайн: hardening build-runner и skills/build против «зависаний» Gradle-сборок

Дата: 2026-07-17. Статус: одобрен пользователем (brainstorming).
Ветка: `build-runner-hardening`.

## Контекст и проблема

Сборки Gradle через `skills/build` + `agents/build-runner` периодически «зависают» и идут в разы дольше обычных ~5 минут. Расследование (форензика `~/.gradle` + проверка фактов харнеса + deep-research, 25/25 утверждений подтверждено) установило цепочку:

1. build-runner не передаёт `timeout` в Bash → действует дефолт 120 с → каждая ~5-минутная сборка превышает его, и Claude Code (v2.1.210+) **уводит команду в фон**; в инструкциях агента нет протокола для этого случая.
2. Агент (haiku) в этой ситуации импровизирует: перезапускает сборку (параллельная сборка в общий `~/.gradle`) или рапортует провал, а скилл разрешает до 3 попыток.
3. Осиротевшие/отменённые клиенты переводят демон в CANCELLED (не переиспользуется, gradle#31679), отмена дольше 10 с гасит демон целиком → лавина холодных демонов (в логах: ~43 за 30 дней, пики 8–10/день), плюс риск реального бага «Timeout waiting to lock journal cache» (gradle#8750/#8375) при параллельных сборках.

Полный отчёт с фактами и ссылками: `docs/gradle-build-runner-hardening-report.md` (локальный, untracked — в git не добавлять).

## Принятые решения

- `model: haiku` → **`model: sonnet`** (подтверждено пользователем; соответствует глобальному правилу «минимум sonnet»). Opus отклонён как избыточный.
- Агенту добавляется только **read-only** диагностика (`jps`, `jstack`, `ps`); право `kill` агенту **не** даётся — восстановление выполняет главная сессия по инструкции скилла. Философия агента «report, don't fix» сохраняется.
- Правки хост-настроек пользователя (`~/.claude/settings.json`, `~/.gradle/gradle.properties`) — **вне скоупа**; в README добавляется рекомендательная секция, т.к. плагин не может задавать env харнеса (подтверждено по докам).
- Таймаут-стратегия (итерация ревью-1, выбор пользователя): агент передаёт `timeout: 1800000`; харнес молча клампит к потолку (эмпирически проверено на текущей версии: значения выше потолка принимаются без ошибки) — 600000 без настройки хоста, 1800000 с `BASH_MAX_TIMEOUT_MS`. README объясняет обе env-переменные честно: BASH_MAX — форграунд для длинных сборок, BASH_DEFAULT — страховка команд без явного timeout.
- Recovery — хирургический (итерация ревью-1, выбор пользователя): убивается только подтверждённый владелец лока (identity-проверка `ps -fp` против PID reuse); чужие демоны (IDE, другие проекты/сессии) — только с подтверждением пользователя. Blanket-kill всех GradleDaemon/KotlinCompileDaemon отвергнут как вектор поражения соседних сборок.
- Агенту добавляется `Bash(sleep:*)` — пейсинг ожидания фоновой сборки (итерация ревью-1). Команда инертная, философию «report, don't fix» не нарушает (решение «без kill» касалось мутирующих действий); без sleep протокол ожидания вырождается в busy-loop с частотой раунд-трипа.
- `--console=plain` — сверх подтверждённых фактов отчёта-расследования (там помечен «опционально»), но принят как обязательный сознательно: безвреден, стабилизирует парсинг логов (ANSI/прогресс-строки), особенно при чтении файла вывода фоновой сборки. Применяется ко ВСЕМ `./gradlew`-вызовам, включая точные команды из Step 0; для Maven симметрично `-B`.
- `model: sonnet` — для всех стеков, не только Gradle: протокол фоновых сборок и классификация INFRA/BUILD одинаковы везде, а ветвление модели по стеку frontmatter'ом не выражается.
- JDK-утилиты (`jps`/`jstack`) агент вызывает по PATH (permission-паттерн `Bash(jps:*)` — префикс-матч, вызовы по абсолютному пути `$JAVA_HOME/bin/jps` он не покрывает — подтверждено по докам permissions); при отсутствии на PATH — пропустить диагностику и отметить это в Details.
- Ветка создана через `git switch -c` (выбор пользователя).

## Изменение 1: `agents/build-runner.md`

### Frontmatter

- `model: haiku` → `model: sonnet`.
- В `tools` добавить: `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)`, `Bash(sleep:*)`.

### Новая секция «Execution Rules (All Stacks)» — сразу после Step 0

Содержание (английский текст файла, тезисно):

1. **Always set an explicit timeout.** Каждый Bash-вызов команды build/test/lint — и любой потенциально долгой команды, включая установку зависимостей (`npm install`, `uv sync`, `poetry install`) — обязан передавать `timeout: 1800000` (30 минут; харнес молча клампит к действующему потолку — 600000 на хосте без `BASH_MAX_TIMEOUT_MS`; проверено экспериментально — значение выше потолка принимается, не отклоняется). На дефолтные 120 с не полагаться — типовая сборка их превышает. Правила действуют и для точных команд вызывающего из Step 0.
2. **One build at a time.** Не запускать новую команду сборки, пока предыдущая не завершилась — включая уведённую в фон.
3. **Протокол «moved to the background»** (сообщение «Command did not complete within its …s timeout and was moved to the background (ID: …)»):
   - команду НЕ перезапускать;
   - поллить, а не перечитывать: цикл `sleep 30` → Grep файла вывода (путь из уведомления) по `BUILD SUCCESSFUL|BUILD FAILED|FAILURE:`; уведомление о завершении задачи приходит в следующем ходу (подтверждено по докам, v2.1.211+) — это бонус, не механизм;
   - по маркеру завершения — Read хвоста файла (offset) и отчёт по фактическому результату, не догадка;
   - **бюджет ожидания**: сборка идёт >~20 мин поллинга или вывод не растёт ~10 мин → прекратить ждать, отчёт INFRASTRUCTURE FAILURE (Cause: `orphaned background build`, Recommended Action: `run daemon recovery procedure first (see build skill)`, в Details — task ID и путь к файлу вывода);
   - не завершать ход, пока сборка идёт и бюджет не исчерпан.
4. **Gradle: `--console=plain` к каждому `./gradlew`-вызову**, включая точные команды вызывающего (если вызывающий сам передал `--console` — не дублировать).
5. **Демонами не управлять**: не выполнять `--stop`, не убивать процессы, не удалять `*.lock` — только диагностировать и отчитываться (см. Infrastructure Failures).
6. DEBUG-строки вида `Waiting to acquire shared lock on daemon addresses registry` — штатный поллинг, не ошибка; в отчёт не выносить. ERROR-вариант `Timeout waiting to lock daemon addresses registry` — инфра-сбой (см. Infrastructure Failures).
7. **Обрезанный вывод**: причину искать в файле вывода через Grep/Read, не судить по видимому хвосту.

### Подраздел «Infrastructure Failures» в Gradle-секции

- Принцип: **не уверен — классифицируй как BUILD FAILED**; recovery не запускается на сомнительных основаниях.
- При `Timeout waiting to lock <cache>… Owner PID: X`: выполнить `ps -fp X` (идентичность процесса: args/проект); опционально `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'` и для живого владельца `jstack X | head -200` — фрагменты в Details. Отчёт INFRASTRUCTURE FAILURE: владелец мёртв или зомби (`Z` — лок уже не держит) → `safe to retry`; жив → `run daemon recovery procedure first (see build skill)`; PID в сообщении отсутствует или `ps` недоступен → обычный BUILD FAILED с ключевыми строками лога.
- Прочие демонные сигнатуры → INFRASTRUCTURE FAILURE / `safe to retry`: `Gradle build daemon disappeared unexpectedly`, `Could not connect to the Gradle daemon`, `Daemon was stopped to free memory`, ERROR-вариант `Timeout waiting to lock daemon addresses registry`.
- False friends (это код, отчёт BUILD FAILED): `Execution failed for task …`, `Could not determine the dependencies of task …`, `Could not resolve all files for configuration …`.
- `jps`/`jstack` не на PATH → пропустить, отметить в Details. Не-Gradle стеки — детекции нет, их сбои идут обычным BUILD FAILED.
- `--no-daemon` не добавлять (контенцию не лечит, противоречит официальной рекомендации Gradle).

### Новый формат отчёта (в «Error Reporting Format»)

```
INFRASTRUCTURE FAILURE

## Cause
[lock timeout | orphaned background build | other environment issue]

## Details
[lock file/cache; owner PID, state (alive/dead/zombie), identity (ps -fp args); key log lines; jps snapshot]

## Background Task ID (if applicable)
[task ID + путь к файлу вывода недостроенной фоновой сборки]

## Recommended Action
[safe to retry | run daemon recovery procedure first (see build skill)]
```

Метки Recommended Action — дословно, без перефразирования (скилл матчит по этим строкам).

### Important Guidelines — дополнить

- Не перезапускать сборку после ухода в фон; поллить по правилам, при исчерпании бюджета — отчёт INFRASTRUCTURE FAILURE (orphaned background build).
- Различать INFRASTRUCTURE FAILURE (проблема окружения/демонов) и BUILD FAILED (проблема кода) — от этого зависит логика ретраев вызывающего.

## Изменение 2: `skills/build/SKILL.md`

### Step 1/Step 2 — последовательная диспетчеризация

- Не отправлять нового build-runner, пока предыдущий не вернул результат — включая цепочку «ktlintFormat → повторная сборка».
- Агент вернулся при живой фоновой сборке (нарушение протокола/гибель агента) → сообщить пользователю; следующий сбой трактовать как INFRASTRUCTURE FAILURE с живым владельцем (recovery перед ретраем).
- Пользователь уточнил запрос во время работы агента → дождаться отчёта, затем новый диспатч с уточнением.

### Step 2 — обработка INFRASTRUCTURE FAILURE (новый пункт)

- Owner PID мёртв → один повтор сразу.
- Owner PID жив или orphaned background build → выполнить процедуру восстановления, затем **один** повтор.
- Malformed-отчёт (без распознаваемого Recommended Action) → трактовать как BUILD FAILED, recovery не запускать.
- Пользователь сообщает о зависшей сборке → выполнить процедуру восстановления напрямую (отчёт агента не требуется).

### Новая секция «Daemon Recovery Procedure» (выполняет главная сессия, не агент)

Оговорка в тексте секции: команды процедуры (`--stop`, `jps`, `kill`, `jstack`, `sleep`) — НЕ build/test/lint-команды; правило «always delegate» на них не распространяется, build-runner-у их не делегировать.

1. `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'` — снимок «до» (для сравнения после `--stop`).
2. `./gradlew --stop` в проекте (останавливает только демоны своей версии Gradle; нет wrapper — пропустить шаг).
3. Хирургически, ТОЛЬКО владелец лока из отчёта агента: `ps -fp <owner pid>` — подтвердить, что это всё ещё Gradle/Kotlin-демон ЭТОГО проекта (защита от PID reuse). Чужой проект/IDE/другая сессия → НЕ убивать, спросить пользователя. PID в отчёте отсутствует (orphaned build, ручной триггер) → шаги 3–4 пропустить: `--stop` + пауза обычно достаточны, рецидив на ретрае принесёт lock-отчёт с PID.
4. Подтверждён и жив → `kill <owner pid>`; `sleep 15`; выжил → `kill -9 <owner pid>`.
5. `sleep 20` перед ретраем (демон в CANCELLED не переиспользуется; мгновенный ретрай плодит новых демонов).
6. Один повтор сборки — он будет медленным (холодные Gradle/Kotlin демоны), медленный ≠ зависший. Ретрай упал с ДРУГИМ живым владельцем → одна повторная identity-проверка по шагу 3, дальше не циклиться — отчёт пользователю. Снова зависает → PID демона через `jps`, `jstack <pid> | head -200`, отчёт пользователю.

### Секция «Output format» — дополнить

- Третий статус: INFRASTRUCTURE FAILURE (+ cause, details, recommended action).

### Limitations — уточнить

- Максимум 4 запуска сборки за вызов скилла: до 3 попыток на ошибках кода + не более 1 ретрая после INFRASTRUCTURE FAILURE; авто-фиксы (ktlintFormat, ruff --fix) запусками не считаются.
- Последовательность защищает только от самодублирования — чужие сессии/IDE делят `~/.gradle`.
- Долгоживущие/watch-команды (bootRun, --continuous, dev-серверы) в build-runner не диспетчеризуются.
- Таймаута диспетчеризации нет: зависший build-runner скилл не обнаружит (известное ограничение).

## Изменение 3: `README.md`

Новая секция «Recommended host setup» (кратко, по одной строке «почему»):

- `.claude/settings.json` (user или project): `{ "env": { "BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "1800000" } }` — плагин не может задать это сам. `BASH_MAX` поднимает потолок per-call: агент всегда просит 30 минут, харнес клампит к потолку → с настройкой длинные сборки идут в форграунде; `BASH_DEFAULT` — страховка для команд без явного timeout (главная сессия, recovery). Merge в существующий settings.json, не замена.
- `~/.gradle/gradle.properties`: `org.gradle.daemon.idletimeout=1800000` — меньше одновременно живущих тяжёлых демонов. Оговорка-трейдофф: первая сборка после долгого простоя — холодный старт.
- Для мульти-JDK машин: `org.gradle.java.installations.auto-detect=false` + `org.gradle.java.installations.paths=…` — закрывает подтверждённый вектор вечного зависания автодетекта тулчейнов. Оговорки: пути подставить свои; не включать, если другие проекты машины полагаются на автодетект.
- Разрешения для recovery: `Bash(jps:*)`, `Bash(kill:*)`, `Bash(jstack:*)` в главной сессии (или подтверждать промпты); процедура идемпотентна — безопасно начать заново. Для диагностики агента JDK `bin` должен быть на PATH.
- Мини-runbook «Quick diagnostics»: `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'`; `ps -fp <pid>`; `jstack <pid> | head -100` + напоминание «никогда не передавать `--no-daemon`».
- Границы поддержки: Unix-like хосты, Claude Code ≥ 2.1.211 (доставка уведомлений о фоновых задачах субагентам).

## Изменение 4: `CHANGELOG.md`

Запись в стиле существующих: hardening build-runner/build skill (timeout discipline, bounded background-build protocol — sleep+grep polling с бюджетом ожидания, расширенная детекция и обработка infrastructure failures, daemon recovery procedure, model haiku→sonnet, host setup docs).

## Вне скоупа

- Правки `~/.claude/settings.json` и `~/.gradle/gradle.properties` пользователя (только документация в README).
- PreToolUse-хук для инъекции `timeout` (поведение `updatedInput` для поля timeout не документировано).
- Изменения детекции стека/JDK (Step 1–2 агента) — работают, форензика проблем не показала.
- Файл `docs/gradle-build-runner-hardening-report.md` остаётся untracked (локальный архив; после мержа можно удалить). `.gitignore` для него не заводим — личный файл автора не должен попадать в публичный репозиторий; защита — явные пути в `git add`.
- Детерминированные механизмы «на вырост» (отложено сознательно, итерация ревью-1): конечный автомат состояний сборки (FOREGROUND → BACKGROUND → COMPLETED | DEADLINE_EXCEEDED), машинные коды `STATUS:`/`ACTION:` в отчётах, межпроцессный lock-wrapper против параллельных сессий. Текущая итерация остаётся minimally invasive markdown; человекочитаемые метки + дословность закрывают парсинг.

## Критерии приёмки

1. `agents/build-runner.md`: `model: sonnet`; в tools есть `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)`, `Bash(sleep:*)` и нет `kill`; секция Execution Rules с правилами timeout (включая dependency installs) / одна-сборка / фон-протокол с полл-циклом и бюджетом ожидания / `--console=plain` для всех `./gradlew` / обрезанный вывод; подраздел Infrastructure Failures с ветками dead/zombie/alive/unknown, расширенными сигнатурами, false friends и правилом «unsure → BUILD FAILED»; формат INFRASTRUCTURE FAILURE с Background Task ID и запретом перефразирования меток; `-B` в Maven-командах.
2. `skills/build/SKILL.md`: последовательная диспетчеризация + маршрутизация возврата при живой сборке + правило запросов «в полёте»; ветки обработки INFRASTRUCTURE FAILURE (включая malformed → BUILD FAILED и ручной триггер по жалобе пользователя); секция Daemon Recovery Procedure с оговоркой о неделегировании, снимком jps и хирургическими шагами `--stop` → identity-проверка владельца (`ps -fp`, защита от PID reuse) → `kill`/`kill -9` только владельца → `sleep` → один повтор (чужие процессы — только через подтверждение пользователя); Output format с третьим статусом; Limitations с арифметикой «максимум 4 запуска, ≤1 инфра-ретрай» и запретом watch-команд; формулировка `build/test/lint/type-check` сохранена.
3. `README.md`: секция Recommended host setup (таймауты, idletimeout с трейдоффом, мульти-JDK с оговорками, recovery permissions, quick-diagnostics runbook, границы поддержки); обновлённая заметка о модели.
4. `CHANGELOG.md`: запись об изменении.
5. Тексты файлов — на английском (без кириллицы), в стиле существующих; отчёт в `docs/` не закоммичен.

## Проверка

- Вычитка изменённых файлов на согласованность (форматы отчётов агента ↔ обработка в скилле; метки — дословно/по префиксу, как зафиксировано в плане).
- Смоук-тесты ДО мержа (вручную, из ветки через `claude --plugin-dir`): (1) сборка >2 мин — идёт с `timeout: 1800000` (кламп к потолку хоста) и `--console=plain`, в форграунде; (2) сборка >10 мин — уходит в фон, агент поллит `sleep 30` + Grep и не перезапускает, отчитывается фактическим результатом; (3) негативный кейс — занятый глобальный lock → INFRASTRUCTURE FAILURE с верным Owner PID и Recommended Action, скилл делает ровно один ретрай.
