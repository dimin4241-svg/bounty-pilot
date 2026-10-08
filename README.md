# Bounty Pilot

**Одна ссылка на репозиторий → проверка scope → аудит → локальный PoC → черновик репорта.**

An evidence-driven Web3 bug bounty workflow for coding agents. Russian progress summaries and English report drafts by default. Original orchestration and checklists; optional integration with Pashov, Trail of Bits, 0xSimao and QuillShield.

## Быстрый старт

Передайте вашему coding-агенту эту команду:

> Install https://github.com/dimin4241-svg/bounty-pilot and run Bounty Pilot on https://github.com/OWNER/TARGET. Read skills/bounty-pilot/SKILL.md and follow it. Keep findings private.

Затем в проекте или чате с установленным навыком:

> Bounty Pilot: https://github.com/OWNER/TARGET

Можно просто прислать ссылку в уже начатом аудите. Ссылка на bounty-программу полезна, но не обязательна для начала анализа исходников. Без правил программы и данных о deployment вывод о пригодности к выплате останется неподтверждённым.

Это **навык для агента с доступом к файлам, Git и тестам**, а не облачный сканер. Для доказательства багов нужны инструменты целевого проекта: например Foundry, Cargo или локальный Solana test harness. Python 3.9+ и Git нужны только для вспомогательного скрипта. Использование модели оплачивается по условиям вашего агента.

## Что внутри

- До трёх проходов с разными задачами вместо бесконечного повторения одного промпта.
- Приоритет изменениям кода, движению активов, интеграциям и непроверенным путям.
- Основные линзы Solidity/EVM, отдельный маршрут Rust/Solana.
- Учёт гипотез: `hypothesis`, `needs-evidence`, `verified`, `refuted`.
- Раздельная оценка технической валидности, scope, deployment и публичных известных проблем.
- Подтверждение через локальный PoC, наблюдаемый результат и контрольный сценарий.
- Обоснованное опровержение: без автоматического отбрасывания по фразе «скорее всего intended».
- Черновики репортов на английском; никакой автоматической отправки.

## Установка вручную

Скопируйте каталог `skills/bounty-pilot` в поддерживаемый вашим агентом каталог skills. Не перезаписывайте существующую установку без просмотра изменений. Если автоматическое обнаружение не поддерживается, укажите агенту полный путь к `skills/bounty-pilot/SKILL.md` и попросите следовать ему. Не нужно устанавливать все внешние наборы.

Агент может читать навык из клона этого репозитория без установки. Поддержка параллельных агентов необязательна: есть последовательный маршрут. Конкретные UI установки зависят от клиента и версии.

## Вспомогательный скрипт

```sh
python3 skills/bounty-pilot/scripts/bounty.py init --repo /path/to/target --out /path/to/private/new-run
python3 skills/bounty-pilot/scripts/bounty.py check --run /path/to/private/new-run
python3 -m unittest discover -s tests -v
```

`init` сохраняет commit, состояние рабочей копии, список отслеживаемых файлов и шаблоны. Он не клонирует проект, не выполняет его код и не проводит аудит. Каталог результата должен быть новым и находиться вне целевого проекта и установленного навыка.

`check` проверяет структуру записей и наличие файлов доказательств. Он **не доказывает истинность находки**, корректность severity, отсутствие приватного дубликата или право на выплату. Пустой список находок также может пройти структурную проверку.

## Optional upstream modules

See [integration guidance](skills/bounty-pilot/references/integrations.md). Modules are not bundled or automatically downloaded. Inspect and pin their revisions before use; record which ones actually ran. Do not nest full multi-pass orchestrators. Upstream licenses remain separate.

## Privacy and responsible use

Run tests locally in a secret-free environment, within authorization and program rules. Do not broadcast exploit transactions. Keep target source, findings, logs, PoCs and credentials out of this public toolkit. Publication of the toolkit does not authorize disclosure of audit results.

## Limitations

No guaranteed vulnerability discovery, payout, novelty or complete coverage. A local fixture test is not a real-world audit benchmark. Unsupported toolchains and unavailable program/deployment information must be reported, never invented. The built-in non-EVM route is narrower than a dedicated ecosystem audit toolkit.

## English quick start

Ask your coding agent to read `skills/bounty-pilot/SKILL.md`, then provide the target repository URL and optionally the bounty program URL. It will model scope, perform distinct review passes, validate candidates locally and prepare private report drafts. Change the explanation language in your request if desired.

## License and attribution

Original package: MIT. See [LICENSE](LICENSE) and [SOURCES.md](SOURCES.md). No affiliation with or endorsement by the linked projects is implied.
