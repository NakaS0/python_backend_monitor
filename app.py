"""CLI entry point for the Suruga-ya monitor application.

このファイルは「コマンド受付係」です。
- どのコマンドを実行するかを受け取る
- 必要な処理（監視実行、UI起動など）へ振り分ける
"""

import argparse
import json
import os
import webbrowser
from urllib.parse import parse_qsl, urlsplit

from dashboard import serve_dashboard
from fixed_targets import FIXED_TARGETS
from scraper import (
    COOKIE_FILE,
    DEFAULT_BASE_URL,
    bootstrap_login_session,
    check_new_items,
    latest_report_file,
)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を定義して解析結果を返す。

    例:
    - `init-session`: 手動ログインしてCookieを保存
    - `check`: 1回だけ監視を実行
    - `watch`: 監視実行後にUIを起動
    - `show-last`: 最新レポートを表示
    - `serve-ui`: UIサーバーのみ起動
    """
    parser = argparse.ArgumentParser(
        description="Suruga-ya update monitor with login/adult-content session support."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-session",
        help="Open Chrome and create session cookies (with optional adult-setting pre-step).",
    )
    init_parser.add_argument(
        "--skip-pre-step",
        action="store_true",
        help="Skip the pre-login step (adult visibility / age confirmation guidance).",
    )

    check_parser = subparsers.add_parser("check", help="Run one update check.")
    check_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of result pages to scan. Omit for no limit.",
    )

    watch_parser = subparsers.add_parser("watch", help="Run update check in a loop.")
    watch_parser.description = "Run one full-page monitoring pass, then open dashboard."
    watch_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of result pages to scan. Omit for no limit.",
    )
    watch_parser.add_argument("--ui-host", default="127.0.0.1")
    watch_parser.add_argument("--ui-port", type=int, default=8080)
    watch_parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Do not auto-open browser when watch ends.",
    )

    subparsers.add_parser(
        "show-last",
        help="Show the latest check result for the target.",
    )
    show_last_parser = subparsers.choices["show-last"]
    show_last_parser.add_argument("--target", default="default")

    ui_parser = subparsers.add_parser(
        "serve-ui",
        help="Serve a local dashboard for check results.",
    )
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8080)

    return parser.parse_args()


def _target_likely_requires_cookie(url: str) -> bool:
    """Heuristic: adult/cookie query parameters usually require a session cookie."""
    try:
        query = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    except Exception:
        return False
    keys = {k.lower() for k, _ in query}
    return "adult_s" in keys or "cookie" in keys


def _warn_cookie_if_needed() -> None:
    """Print an actionable hint when session cookies are likely required."""
    if os.path.exists(COOKIE_FILE):
        return
    if not any(_target_likely_requires_cookie(t["url"]) for t in FIXED_TARGETS):
        return
    print("\n[WARN] Cookie file not found: surugaya_cookies.json")
    print("[WARN] Some configured URLs likely need a logged-in/adult-enabled session.")
    print("[WARN] Run `python app.py init-session` and then retry `python app.py check`.\n")


def main() -> None:
    """引数に応じてアプリの実行ルートを決めるメイン関数。"""
    args = parse_args()

    if args.command == "init-session":
        open_url = FIXED_TARGETS[0]["url"] if FIXED_TARGETS else DEFAULT_BASE_URL
        bootstrap_login_session(
            open_url=open_url,
            use_pre_step=not args.skip_pre_step,
        )
        return

    if args.command == "check":
        _warn_cookie_if_needed()
        for target in FIXED_TARGETS:
            print(f"\n=== Target: {target['name']} ({target['id']}) ===")
            check_new_items(
                max_pages=args.max_pages,
                base_url=target["url"],
                target_id=target["id"],
            )
        return

    if args.command == "watch":
        _warn_cookie_if_needed()
        for target in FIXED_TARGETS:
            print(f"\n=== Target: {target['name']} ({target['id']}) ===")
            check_new_items(
                max_pages=args.max_pages,
                base_url=target["url"],
                target_id=target["id"],
            )
        ui_url = f"http://{args.ui_host}:{args.ui_port}"
        print("\nMonitoring finished (reached last page). Starting dashboard...")
        if not args.no_open_browser:
            webbrowser.open(ui_url)
        serve_dashboard(host=args.ui_host, port=args.ui_port)
        return

    if args.command == "show-last":
        report_file = latest_report_file(args.target)
        if not os.path.exists(report_file):
            print(f"No report file found: {report_file}")
            return

        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.command == "serve-ui":
        serve_dashboard(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
