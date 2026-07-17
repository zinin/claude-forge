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
- Ветка создана через `git switch -c` (выбор пользователя).

## Изменение 1: `agents/build-runner.md`

### Frontmatter

- `model: haiku` → `model: sonnet`.
- В `tools` добавить: `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)`.

### Новая секция «Execution Rules (All Stacks)» — сразу после Step 0

Содержание (английский текст файла, тезисно):

1. **Always set an explicit timeout.** Каждый Bash-вызов команды build/test/lint обязан передавать `timeout: 600000` (10 минут — потолок харнеса по умолчанию). На дефолтные 120 с не полагаться — типовая сборка их превышает.
2. **One build at a time.** Не запускать новую команду сборки, пока предыдущая не завершилась — включая уведённую в фон.
3. **Протокол «moved to the background»** (сообщение «Command did not complete within its …s timeout and was moved to the background (ID: …)»):
   - команду НЕ перезапускать;
   - ждать уведомления о завершении задачи; промежуточно можно читать файл вывода через Read;
   - не завершать свой ход, пока сборка идёт; отчитываться только по фактическому финальному результату.
4. **Демонами не управлять**: не выполнять `--stop`, не убивать процессы, не удалять `*.lock` — только диагностировать и отчитываться (см. Infrastructure Failures).
5. DEBUG-строки вида `Waiting to acquire shared lock on daemon addresses registry` — штатный поллинг, не ошибка; в отчёт не выносить.

### Подраздел «Infrastructure Failures» в Gradle-секции

- При `Timeout waiting to lock <cache>… Owner PID: X`: выполнить `ps -p X`; отчитаться форматом INFRASTRUCTURE FAILURE, указав: владелец жив (вероятно, подвисший демон → вызывающему нужна процедура восстановления из скилла) или мёртв (безопасно повторить — локи самовосстанавливаются).
- `--no-daemon` не добавлять (контенцию не лечит, противоречит официальной рекомендации Gradle).
- К Gradle-командам добавлять `--console=plain` (стабильный неинтерактивный вывод).

### Новый формат отчёта (в «Error Reporting Format»)

```
INFRASTRUCTURE FAILURE

## Cause
[lock timeout | orphaned background build | other]

## Details
[lock file, owner PID and its state (alive/dead), key log lines]

## Recommended Action
[safe to retry | run daemon recovery procedure first (see build skill)]
```

### Important Guidelines — дополнить

- Не перезапускать сборку после ухода в фон; ждать результата.
- Различать INFRASTRUCTURE FAILURE (проблема окружения/демонов) и BUILD FAILED (проблема кода) — от этого зависит логика ретраев вызывающего.

## Изменение 2: `skills/build/SKILL.md`

### Step 1/Step 2 — последовательная диспетчеризация

- Не отправлять нового build-runner, пока предыдущий не вернул результат — включая цепочку «ktlintFormat → повторная сборка».

### Step 2 — обработка INFRASTRUCTURE FAILURE (новый пункт)

- Owner PID мёртв → один повтор сразу.
- Owner PID жив → выполнить процедуру восстановления, затем **один** повтор после паузы 15–30 с.

### Новая секция «Daemon Recovery Procedure» (выполняет главная сессия, не агент)

1. `./gradlew --stop` в проекте (важно: останавливает только демоны своей версии Gradle).
2. `jps` → найти выживших `GradleDaemon` / `KotlinCompileDaemon`.
3. `kill <pid>` выжившим; подождать ~15 с; несдавшимся — `kill -9`.
4. Пауза 15–30 с (демон в CANCELLED не переиспользуется; мгновенный ретрай плодит новых демонов).
5. Один повтор сборки. Если снова зависает — `jstack <pid демона>` и отчёт пользователю; не зацикливаться.

### Limitations — уточнить

- До 3 попыток для ошибок сборки (как сейчас); максимум 1 повтор для инфраструктурных сбоев.

## Изменение 3: `README.md`

Новая секция «Recommended host setup» (кратко, по одной строке «почему»):

- `.claude/settings.json` (user или project): `{ "env": { "BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "1800000" } }` — плагин не может задать это сам; без этого команды >2 мин уходят в фон (агент теперь это переживает, но с настройкой сборки идут в форграунде).
- `~/.gradle/gradle.properties`: `org.gradle.daemon.idletimeout=1800000` — меньше одновременно живущих тяжёлых демонов.
- Для мульти-JDK машин: `org.gradle.java.installations.auto-detect=false` + `org.gradle.java.installations.paths=…` — закрывает подтверждённый вектор вечного зависания автодетекта тулчейнов.

## Изменение 4: `CHANGELOG.md`

Запись в стиле существующих: hardening build-runner/build skill (timeout discipline, background-build protocol, infrastructure-failure handling, daemon recovery procedure, model haiku→sonnet, host setup docs).

## Вне скоупа

- Правки `~/.claude/settings.json` и `~/.gradle/gradle.properties` пользователя (только документация в README).
- PreToolUse-хук для инъекции `timeout` (поведение `updatedInput` для поля timeout не документировано).
- Изменения детекции стека/JDK (Step 1–2 агента) — работают, форензика проблем не показала.
- Файл `docs/gradle-build-runner-hardening-report.md` остаётся untracked.

## Критерии приёмки

1. `agents/build-runner.md`: `model: sonnet`; в tools есть `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)` и нет `kill`; секция Execution Rules с правилами timeout/одна-сборка/фон-протокол; подраздел Infrastructure Failures; формат INFRASTRUCTURE FAILURE.
2. `skills/build/SKILL.md`: последовательная диспетчеризация; ветка обработки INFRASTRUCTURE FAILURE; секция Daemon Recovery Procedure с шагами `--stop` → `jps` → `kill`/`kill -9` → пауза → один повтор; лимит 1 ретрай для инфра-сбоев.
3. `README.md`: секция Recommended host setup с тремя пунктами выше.
4. `CHANGELOG.md`: запись об изменении.
5. Тексты файлов — на английском, в стиле существующих; отчёт в `docs/` не закоммичен.

## Проверка

- Вычитка изменённых файлов на согласованность (форматы отчётов агента ↔ обработка в скилле).
- Смоук-тест после мержа (вручную): диспетчеризовать build-runner на реальном Gradle-проекте с сборкой >2 мин и убедиться, что команда идёт с `timeout: 600000`, а при уходе в фон агент ждёт результат, не перезапуская сборку.
