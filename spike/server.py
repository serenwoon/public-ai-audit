"""로컬 서버 — 표준 라이브러리만. 웹 한 장 + 감리 API + 카카오 스킬(콜백 실측 포함).

  GET  /            public/index.html (웹 한 장)
  GET  /health
  POST /audit       {"text","situation"} → 감리 JSON (스텁 엔진)
  POST /skill       카카오 스킬. 「지연 N」이면 N초 뒤 콜백(실측용), 아니면 감리 결과를 카드 3개로

세 값을 실측한다 — ① 「전달」 메시지의 도착 형태(logs/requests.jsonl) ② 콜백 URL 실림 ③ 콜백 허용 초(logs/callbacks.jsonl)
실행:  python spike/server.py   (PORT, 기본 8000)   노출: cloudflared tunnel --url http://localhost:8000
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402
import kakao  # noqa: E402
import share_link  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
INDEX = ROOT / "public" / "index.html"
SHARE_JS = ROOT / "public" / "share.js"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _append(name: str, record: dict) -> None:
    with (LOG_DIR / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def post_callback(callback_url: str, body: dict, started: float, delay: int) -> None:
    """delay초 뒤 콜백 URL로 최종 응답을 보내고 결과를 기록한다."""
    time.sleep(delay)
    elapsed = round(time.monotonic() - started, 2)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(callback_url, data=data, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    rec = {"ts": _now(), "delay_requested": delay, "elapsed_sec": elapsed, "callback_url": callback_url}
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            rec["status"] = resp.status
            rec["body"] = resp.read().decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["body"] = e.read().decode("utf-8", "replace")[:500]
    except Exception as e:  # noqa: BLE001 — 스파이크: 무엇이든 기록
        rec["status"] = "EXC"
        rec["body"] = repr(e)
    _append("callbacks.jsonl", rec)
    print(f"[callback] delay={delay}s elapsed={elapsed}s -> {rec['status']} {rec['body'][:120]}", flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "public-ai-audit-spike/0.2"

    def _send(self, status: int, data: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj: dict, status: int = 200) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        obj, err = kakao.decode_json(raw)
        return obj if err is None else {"_error": err, "_raw": raw.decode("utf-8", "replace")[:2000]}

    def _base_url(self) -> str:
        host = self.headers.get("x-forwarded-host") or self.headers.get("host") or f"localhost:{self.server.server_address[1]}"
        proto = self.headers.get("x-forwarded-proto") or ("https" if "trycloudflare" in host or "vercel" in host else "http")
        return f"{proto}://{host}"

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif path == "/share.js":
            self._send(200, SHARE_JS.read_bytes(), "application/javascript; charset=utf-8")
        elif path.startswith("/health"):
            self._json({"ok": True, "engine": engine.ENGINE, "ts": _now()})
        elif path.startswith("/audit"):
            self._json({"ok": True, "usage": "POST {text, situation?}"})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        started = time.monotonic()
        path = self.path.split("?", 1)[0]
        payload = self._read_json()

        if path.startswith("/audit"):
            text = (payload.get("text") or "").strip()
            if not text:
                self._json({"error": "text가 비었습니다"}, 400)
                return
            today = None
            if payload.get("today") is not None:
                today = share_link.parse_day(payload.get("today"))
                if today is None:
                    self._json({"error": "today 형식은 YYYY-MM-DD 입니다"}, 400)
                    return
            self._json(engine.audit(text[:8000], (payload.get("situation") or "").strip()[:200], today=today))
            return

        if not path.startswith("/skill"):
            self._json({"error": "not found"}, 404)
            return

        # ① 원문 그대로 기록 — 「전달」 메시지의 형태를 보는 것이 목적
        _append("requests.jsonl", {
            "ts": _now(), "path": self.path,
            "headers": {k: v for k, v in self.headers.items() if k.lower() in ("content-type", "user-agent", "x-forwarded-for")},
            "payload": payload,
        })
        req = kakao.parse_request(payload)
        delay = kakao.parse_delay(req["utterance"])
        print(f"[skill] user={req['user_id']} cb={'O' if req['callback_url'] else 'X'} delay={delay} len={len(req['utterance'])}", flush=True)

        if delay is not None and req["callback_url"]:          # ③ 콜백 실측
            final = kakao.simple_text(f"콜백 도착 — 요청 {delay}초 뒤에 보냈어요.\n{_now()}")
            threading.Thread(target=post_callback, args=(req["callback_url"], final, started, delay), daemon=True).start()
            self._json(kakao.callback_wait(f"감리 중이에요. {delay}초 뒤에 결과를 보낼게요."))
            return
        if delay is not None:                                  # ② 콜백 URL 없음
            self._json(kakao.simple_text(
                "콜백 URL이 요청에 없어요.\n오픈빌더 블록 상세 > 더보기(…) > Callback API 설정이 켜져 있는지, 봇을 배포했는지 확인하세요.\n(봇테스트에서는 콜백이 안 옵니다)"))
            return
        if not req["utterance"]:
            self._json(kakao.simple_text("AI가 준 답을 그대로 붙여 넣거나 이 채팅으로 전달해 주세요."))
            return
        self._json(kakao.audit_outputs(engine.audit(req["utterance"]), self._base_url(), text=req["utterance"]))

    def log_message(self, fmt, *args):  # 기본 access log는 조용히
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"spike server on http://localhost:{port}  (GET /, POST /audit, POST /skill, GET /health)  logs -> {LOG_DIR}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
