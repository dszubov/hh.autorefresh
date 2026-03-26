#!/usr/bin/env python3
# coding: utf-8

import argparse
import logging
import os
import platform
import sys
import time

import requests

LOG_FILENAME = 'hh.log'
HH_API_URL = 'https://api.hh.ru'
HH_OAUTH_URL = 'https://hh.ru/oauth/token'


def send_message(title: str, message: str) -> None:
    platform_name = platform.system()
    if platform_name == 'Linux':
        os.system(f'notify-send "{title}" "{message}"')
    elif platform_name == 'Darwin':
        os.system(
            f"osascript -e 'display notification \"{message}\" with title \"{title}\"'"
        )


def configure_logging() -> None:
    logging.basicConfig(
        filename=LOG_FILENAME,
        level=logging.DEBUG,
        format='%(levelname)-8s [%(asctime)s]  %(message)s',
    )


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    }

    response = requests.post(HH_OAUTH_URL, data=payload, timeout=30)
    logging.debug('OAuth response: %s %s', response.status_code, response.text)

    if response.status_code != 200:
        raise RuntimeError(
            f'Не удалось обновить access token. HTTP {response.status_code}: {response.text}'
        )

    data = response.json()
    access_token = data.get('access_token')

    if not access_token:
        raise RuntimeError('Ответ HH OAuth не содержит access_token')

    new_refresh_token = data.get('refresh_token')
    if new_refresh_token and new_refresh_token != refresh_token:
        logging.warning(
            'HH вернул новый refresh_token. Обновите секрет HH_REFRESH_TOKEN в GitHub.'
        )

    return access_token


def get_access_token(args: argparse.Namespace) -> str:
    if args.token:
        return args.token

    if args.client_id and args.client_secret and args.refresh_token:
        return refresh_access_token(args.client_id, args.client_secret, args.refresh_token)

    raise ValueError(
        'Передайте либо --token, либо набор --client-id --client-secret --refresh-token'
    )


def publish_resume(access_token: str, resume_id: str) -> int:
    url = f'{HH_API_URL}/resumes/{resume_id}/publish'
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.post(url, headers=headers, timeout=30)
    logging.debug('Publish response: %s %s', response.status_code, response.text)
    return response.status_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Автоматическое обновление резюме на hh.ru'
    )
    parser.add_argument('--resume-id', required=True, help='ID резюме hh.ru')
    parser.add_argument('--token', help='Прямой access token hh.ru')
    parser.add_argument('--client-id', help='OAuth client_id приложения HH')
    parser.add_argument('--client-secret', help='OAuth client_secret приложения HH')
    parser.add_argument('--refresh-token', help='OAuth refresh_token пользователя HH')
    return parser.parse_args()


def main() -> int:
    configure_logging()
    logging.debug('Script started at %s', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))

    args = parse_args()

    try:
        access_token = get_access_token(args)
        status_code = publish_resume(access_token, args.resume_id)
    except Exception as exc:  # noqa: BLE001
        logging.exception('Ошибка выполнения: %s', exc)
        send_message('Error', str(exc))
        print(str(exc), file=sys.stderr)
        return 1

    if status_code == 429:
        send_message('Error', 'You are trying to update your resume too often')
        return 1
    if status_code == 403:
        send_message('Error', 'Token expired or invalid. Re-authorize in HH OAuth app.')
        return 1
    if status_code in (200, 204):
        send_message('Success', 'Your resume was updated')
        return 0

    send_message('Error', f'Unexpected status code: {status_code}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
