# Автоматическое обновление резюме на HeadHunter через GitHub Actions

[![Refresh Resume](https://github.com/dszubov/hh.autorefresh/actions/workflows/refresh.yml/badge.svg?branch=master)](https://github.com/dszubov/hh.autorefresh/actions/workflows/refresh.yml)

Этот проект позволяет автоматически обновлять ваше резюме на HeadHunter (hh.ru) с использованием GitHub Actions.

## Как это работает

Скрипт `hh.py` поддерживает **автоматическое получение access token из refresh token**:

1. GitHub Actions берет `HH_CLIENT_ID`, `HH_CLIENT_SECRET`, `HH_REFRESH_TOKEN` из секретов.
2. Скрипт делает запрос в OAuth (`https://hh.ru/oauth/token`) с `grant_type=refresh_token`.
3. Полученный `access_token` сразу используется для `POST /resumes/{resume_id}/publish`.

Таким образом, вам не нужно вручную обновлять `HH_TOKEN` перед каждым запуском.

## Как использовать

1. **Создайте форк [основного репозитория](https://github.com/dszubov/hh.autorefresh)**

2. **Настройте секреты в вашем форке**:
   - `HH_RESUME_ID`: идентификатор резюме
   - `HH_CLIENT_ID`: OAuth `client_id` из вашего приложения HH
   - `HH_CLIENT_SECRET`: OAuth `client_secret` из вашего приложения HH
   - `HH_REFRESH_TOKEN`: refresh token (получается один раз при первичной OAuth-авторизации)

3. **Запустите GitHub Actions**:
   - Workflow `refresh.yml` запускается по расписанию каждые 4 часа.


## Где взять данные для токена (по документации HH)

Официальные источники:
- Портал разработчика: `https://dev.hh.ru/`
- Раздел OAuth в OpenAPI/ReDoc: `https://api.hh.ru/openapi/redoc#section/Avtorizaciya`
- Личный кабинет приложений: `https://dev.hh.ru/admin`

Что и где брать:
1. `HH_CLIENT_ID` и `HH_CLIENT_SECRET`
   - Создайте приложение в `https://dev.hh.ru/admin` (кнопка «Добавить приложение»).
   - После одобрения приложения возьмите `client_id` и `client_secret` в карточке приложения.
2. `HH_REFRESH_TOKEN`
   - Нужен только для первичной настройки: пройдите OAuth Authorization Code flow из раздела OAuth документации.
   - Получите `code` через redirect URI, затем обменяйте `code` на токены через `POST https://hh.ru/oauth/token`.
   - Сохраните `refresh_token` в GitHub Secret `HH_REFRESH_TOKEN`; дальше workflow сам получает новый `access_token` при каждом запуске.
3. `HH_RESUME_ID`
   - Возьмите из URL резюме: `https://hh.ru/resume/<resume_id>`.

Пример обмена `code` на токены:

```bash
curl -X POST 'https://hh.ru/oauth/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=authorization_code' \
  -d 'client_id=<HH_CLIENT_ID>' \
  -d 'client_secret=<HH_CLIENT_SECRET>' \
  -d 'code=<CODE_FROM_REDIRECT>' \
  -d 'redirect_uri=<REDIRECT_URI>'
```

## Режимы запуска скрипта

### 1) Рекомендуемый: через refresh token

```bash
python hh.py \
  --resume-id <resume_id> \
  --client-id <client_id> \
  --client-secret <client_secret> \
  --refresh-token <refresh_token>
```

### 2) Обратная совместимость: прямой access token

```bash
python hh.py --resume-id <resume_id> --token <access_token>
```

## Важные примечания

- `access_token` обновляется автоматически на каждом запуске из `refresh_token` (вручную каждый раз получать его не нужно).
- `refresh_token` обычно заводится один раз при первичной OAuth-настройке.
- Если нужно поменять периодичность — измените `cron` в `.github/workflows/refresh.yml`.
- При ошибках авторизации проверьте актуальность OAuth-данных приложения и refresh token.

## Вклад

Если есть идеи по улучшению, создавайте issue и pull request.
