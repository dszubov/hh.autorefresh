#!/usr/bin/env python3
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from nacl import encoding, public


HH_TOKEN_URL = "https://api.hh.ru/token"
HH_PUBLISH_URL = "https://api.hh.ru/resumes/{resume_id}/publish"
GITHUB_API_URL = "https://api.github.com"
TOKEN_EXPIRY_SKEW_SECONDS = 60


def log(message):
    print(message, flush=True)


def fail(message, exit_code=1):
    print(message, file=sys.stderr, flush=True)
    raise SystemExit(exit_code)


def env(name, default=None):
    return os.environ.get(name, default)


def require_env(name):
    value = env(name)
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def add_mask(value):
    if value:
        print(f"::add-mask::{value}", flush=True)


def parse_github_repository():
    repository = require_env("GITHUB_REPOSITORY")
    if "/" not in repository:
        fail(f"Unexpected GITHUB_REPOSITORY value: {repository}")
    owner, repo = repository.split("/", 1)
    return owner, repo


def parse_expiry(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        fail(f"Invalid HH_TOKEN_EXPIRES_AT value: {raw_value} ({exc})")


def is_token_expired(expires_at):
    if expires_at is None:
        return True
    now = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRY_SKEW_SECONDS)
    return now >= expires_at


def hh_token_request(payload):
    response = requests.post(
        HH_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        timeout=30,
    )
    if response.status_code != 200:
        fail(
            "HH token request failed: "
            f"status={response.status_code} body={response.text}"
        )
    data = response.json()
    for key in ("access_token", "refresh_token", "expires_in"):
        if key not in data:
            fail(f"HH token response missing field: {key}")
    return data


def bootstrap_token_pair(client_id, client_secret, redirect_uri, authorization_code):
    log("Bootstrapping initial HH user token pair from authorization code.")
    return hh_token_request(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": authorization_code,
        }
    )


def refresh_token_pair(refresh_token):
    log("Refreshing expired HH token pair.")
    return hh_token_request(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )


def compute_expires_at(expires_in_seconds):
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in_seconds))
    return expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_request(method, url, token, **kwargs):
    response = requests.request(method, url, headers=github_headers(token), timeout=30, **kwargs)
    if response.status_code >= 400:
        fail(
            "GitHub API request failed: "
            f"method={method} url={url} status={response.status_code} body={response.text}"
        )
    return response


def encrypt_secret(public_key_base64, secret_value):
    public_key = public.PublicKey(public_key_base64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def upsert_github_secret(owner, repo, writer_token, name, value):
    add_mask(value)
    key_response = github_request(
        "GET",
        f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/secrets/public-key",
        writer_token,
    ).json()
    encrypted_value = encrypt_secret(key_response["key"], value)
    github_request(
        "PUT",
        f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/secrets/{name}",
        writer_token,
        json={
            "encrypted_value": encrypted_value,
            "key_id": key_response["key_id"],
        },
    )


def persist_hh_state(owner, repo, writer_token, access_token, refresh_token, expires_at):
    log("Persisting rotated HH credentials to GitHub Actions secrets.")
    secrets_to_update = {
        "HH_ACCESS_TOKEN": access_token,
        "HH_REFRESH_TOKEN": refresh_token,
        "HH_TOKEN_EXPIRES_AT": expires_at,
    }
    for name, value in secrets_to_update.items():
        upsert_github_secret(owner, repo, writer_token, name, value)


def publish_resume(access_token, resume_id):
    response = requests.post(
        HH_PUBLISH_URL.format(resume_id=resume_id),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    if response.status_code in (200, 204):
        log(f"Resume publish succeeded with status {response.status_code}.")
        return

    fail(
        "Resume publish failed: "
        f"status={response.status_code} body={response.text}"
    )


def main():
    owner, repo = parse_github_repository()

    writer_token = require_env("GH_SECRETS_WRITER_PAT")
    client_id = require_env("HH_CLIENT_ID")
    client_secret = require_env("HH_CLIENT_SECRET")
    resume_id = require_env("HH_RESUME_ID")

    access_token = env("HH_ACCESS_TOKEN")
    refresh_token = env("HH_REFRESH_TOKEN")
    expires_at_raw = env("HH_TOKEN_EXPIRES_AT")
    authorization_code = env("HH_AUTHORIZATION_CODE")
    redirect_uri = env("HH_REDIRECT_URI", "http://localhost:8080")

    for value in (writer_token, client_id, client_secret, access_token, refresh_token, authorization_code):
        add_mask(value)

    expires_at = parse_expiry(expires_at_raw)
    token_pair_changed = False

    if refresh_token and access_token and not is_token_expired(expires_at):
        log("Existing HH access token is still valid. Skipping token refresh.")
    elif refresh_token:
        token_data = refresh_token_pair(refresh_token)
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        expires_at_raw = compute_expires_at(token_data["expires_in"])
        token_pair_changed = True
    elif authorization_code:
        token_data = bootstrap_token_pair(client_id, client_secret, redirect_uri, authorization_code)
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        expires_at_raw = compute_expires_at(token_data["expires_in"])
        token_pair_changed = True
    else:
        fail(
            "HH credentials are not bootstrapped. "
            "Provide HH_REFRESH_TOKEN in secrets or pass HH_AUTHORIZATION_CODE in workflow_dispatch."
        )

    if not access_token:
        fail("HH_ACCESS_TOKEN is empty after bootstrap/refresh flow.")
    if not refresh_token:
        fail("HH_REFRESH_TOKEN is empty after bootstrap/refresh flow.")
    if not expires_at_raw:
        fail("HH_TOKEN_EXPIRES_AT is empty after bootstrap/refresh flow.")

    if token_pair_changed:
        persist_hh_state(owner, repo, writer_token, access_token, refresh_token, expires_at_raw)

    publish_resume(access_token, resume_id)

    log(
        json.dumps(
            {
                "status": "ok",
                "token_pair_changed": token_pair_changed,
                "expires_at": expires_at_raw,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
