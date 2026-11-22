#!/usr/bin/env python3
"""Translate an English text file to Japanese through an OpenAI-compatible chat API.

Configuration is read from a fixed file, .config, next to this script:

    URL=https://api.openai.com/v1
    API=sk-...
    MODEL=gpt-4o-mini

URL is the chat service base. If it does not already end in /chat/completions,
that path is appended. The same file works for any service that accepts the
OpenAI chat completions request format.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / ".config"

SYSTEM_MESSAGE = (
    "あなたは英語から日本語への翻訳者です。"
    "渡された英語だけを自然な日本語に変換し、解説や前置きは付けません。"
)
USER_INSTRUCTION = (
    "添付の英語テキストを日本語に変換してください。"
    "意味と段落構成を保ち、変換結果だけを返してください。\n\n"
    "----- ENGLISH TEXT -----\n"
)


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def load_config(path: Path) -> dict[str, str]:
    if not path.is_file():
        message = f"設定ファイルが見つかりません: {path}"
        example = path.with_name(".config.example")
        if example.is_file():
            message += f"。{example.name} をコピーして API、URL、MODEL を記入してください"
        raise SystemExit(message)

    values: dict[str, str] = {}
    text = path.read_text(encoding="utf-8-sig")
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"{path}:{lineno}: KEY=VALUE 形式で記述してください")
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key:
            raise SystemExit(f"{path}:{lineno}: キーが空です")
        values[key] = value
    return values


def require_setting(config: dict[str, str], key: str, path: Path) -> str:
    value = config.get(key, "").strip()
    if not value:
        raise SystemExit(f"{path}: {key} を設定してください")
    return value


def resolve_chat_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("URL は http:// または https:// で始まるアドレスにしてください")
    path = parsed.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path = f"{path}/chat/completions"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def build_user_message(english: str) -> str:
    return f"{USER_INSTRUCTION}{english.strip()}\n"


def extract_content(body: object) -> str:
    if not isinstance(body, dict):
        raise ValueError("応答がJSONオブジェクトではありません")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("choices がありません")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("message がありません")
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_part = item.get("text")
                if isinstance(text_part, str):
                    parts.append(text_part)
        text = "".join(parts)
    else:
        raise ValueError("content がありません")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("翻訳結果が空です")
    return text + "\n"


def translate(english: str, *, api_key: str, url: str, model: str, timeout: float) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": build_user_message(english)},
        ],
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "translation-cli/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if len(detail) > 2000:
            detail = detail[:2000] + "..."
        suffix = f": {detail}" if detail else ""
        raise SystemExit(f"APIリクエストに失敗しました ({exc.code}){suffix}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"APIに接続できませんでした: {exc.reason}") from exc

    try:
        body = json.loads(raw)
        return extract_content(body)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"APIの応答形式が想定と異なります: {exc}") from exc


def default_output_path(source: Path) -> Path:
    return source.with_name(f"{source.stem}.ja{source.suffix or '.txt'}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="英語テキストファイルを日本語に変換します。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "設定ファイルはスクリプトと同じディレクトリの .config です。\n"
            "例:\n"
            "  URL=https://api.openai.com/v1\n"
            "  API=sk-...\n"
            "  MODEL=gpt-4o-mini\n\n"
            "URL の末尾が /chat/completions でなければ自動で付けます。\n"
            "OpenAI互換のチャットAPIであれば、URL と MODEL を差し替えて使えます。"
        ),
    )
    parser.add_argument("input", type=Path, help="英語テキストファイル")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="日本語の出力先。省略時は入力ファイル名に .ja を付けたファイル",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"設定ファイル (既定: {DEFAULT_CONFIG})",
    )
    parser.add_argument("--timeout", type=float, default=180, help="HTTPタイムアウト秒 (既定: 180)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = parse_args(argv)
    config = load_config(args.config)
    api_key = require_setting(config, "API", args.config)
    url = resolve_chat_url(require_setting(config, "URL", args.config))
    model = require_setting(config, "MODEL", args.config)

    source = args.input
    if not source.is_file():
        raise SystemExit(f"入力ファイルが見つかりません: {source}")
    try:
        english = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"入力ファイルをUTF-8として読めません: {source}") from exc
    if not english.strip():
        raise SystemExit(f"入力ファイルが空です: {source}")

    japanese = translate(english, api_key=api_key, url=url, model=model, timeout=args.timeout)
    output = args.output or default_output_path(source)
    try:
        output.write_text(japanese, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SystemExit(f"出力ファイルを書き出せません: {output}: {exc}") from exc
    print(f"書き出しました: {output}")


if __name__ == "__main__":
    main()
