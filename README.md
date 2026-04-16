# Автоматическое обновление резюме на HeadHunter через GitHub Actions

[![Refresh Resume](https://github.com/dszubov/hh.autorefresh/actions/workflows/refresh.yml/badge.svg?branch=master)](https://github.com/dszubov/hh.autorefresh/actions/workflows/refresh.yml)

Этот проект автоматически поднимает резюме на hh.ru через GitHub Actions и сам поддерживает в актуальном состоянии пользовательскую пару `access_token` / `refresh_token`.

## Что изменилось

Старая схема требовала вручную обновлять `HH_TOKEN` в GitHub Secrets после истечения токена.

Новая схема работает так:

1. один раз получаете пользовательскую пару токенов hh.ru;
2. кладёте её в GitHub Secrets;
3. workflow сам проверяет срок жизни токена;
4. при истечении workflow обновляет пару токенов через `refresh_token`;
5. новые значения сразу записываются обратно в GitHub Secrets;
6. после этого workflow публикует резюме.

При штатной работе повторно проходить OAuth каждые 14 дней не нужно.

## Secrets

Нужны следующие `Actions secrets`:

- `GH_SECRETS_WRITER_PAT` — fine-grained PAT с правом `Secrets: Read and write` только на этот репозиторий
- `HH_CLIENT_ID`
- `HH_CLIENT_SECRET`
- `HH_RESUME_ID`
- `HH_ACCESS_TOKEN`
- `HH_REFRESH_TOKEN`
- `HH_TOKEN_EXPIRES_AT`

`HH_TOKEN_EXPIRES_AT` хранится как UTC timestamp в ISO-формате, например `2026-04-30T10:10:49Z`.

## Первичный bootstrap

Перед первым автономным запуском нужно один раз получить пользовательскую пару `access_token` / `refresh_token`.

В репозитории предусмотрен recovery/bootstrap path через `workflow_dispatch` input `authorization_code`, но удобнее сначала получить первую пару локально и положить её в secrets.

После этого расписание будет работать автономно.

## Ручной recovery

Если цепочка refresh сломалась, можно вручную запустить workflow и передать новый `authorization_code` через `workflow_dispatch`.

Это требуется только в аварийных случаях, например если:

- токен был отозван;
- изменилась парольная/безопасностная политика аккаунта hh.ru;
- новая токен-пара не была сохранена после refresh;
- были перевыпущены credentials приложения.

## Расписание

По умолчанию workflow запускается каждые 4 часа:

```yaml
schedule:
  - cron: "56 */4 * * *"
```

При необходимости расписание можно изменить в `.github/workflows/refresh.yml`.

## Как работает скрипт

`hh.py` в одном запуске выполняет весь цикл:

- проверяет текущий `HH_ACCESS_TOKEN`;
- при необходимости обновляет токены через HH API;
- сохраняет новую пару токенов в GitHub Secrets через GitHub REST API;
- вызывает `POST /resumes/{resume_id}/publish`;
- завершает workflow по нормальным exit code, без парсинга лог-файла.

## Ограничения

- Первый пользовательский bootstrap всё равно нужен, потому что hh.ru требует `authorization_code` для получения первой пользовательской токен-пары.
- Для записи секретов workflow использует отдельный GitHub PAT из `GH_SECRETS_WRITER_PAT`.

## Вклад

Pull request и issue приветствуются.
