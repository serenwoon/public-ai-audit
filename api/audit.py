"""Vercel 함수 — POST /api/audit  {"text", "situation"?, "today"?: "YYYY-MM-DD"} → 감리 JSON.

today 는 결과 링크로 열었을 때 카카오에서 본 날과 같은 날 기준으로 다시 계산하려고 받는다. 없으면 오늘(한국 시간).
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spike"))
import engine  # noqa: E402
import kakao  # noqa: E402
import share_link  # noqa: E402

MAX_TEXT = 8000


class handler(BaseHTTPRequestHandler):  # noqa: N801 — Vercel 규약
    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        self._json(200, {"ok": True, "engine": engine.ENGINE, "usage": "POST {text, situation?}"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body, err = kakao.decode_json(self.rfile.read(length) if length else b"")
        if err:
            self._json(400, {"error": err})
            return
        text = (body.get("text") or "").strip()
        if not text:
            self._json(400, {"error": "text가 비었습니다"})
            return
        if len(text) > MAX_TEXT:
            self._json(413, {"error": f"text가 너무 깁니다 (최대 {MAX_TEXT}자)"})
            return
        today = None
        if body.get("today") is not None:
            today = share_link.parse_day(body.get("today"))
            if today is None:
                self._json(400, {"error": "today 형식은 YYYY-MM-DD 입니다"})
                return
        self._json(200, engine.audit(text, (body.get("situation") or "").strip()[:200], today=today))

    def log_message(self, fmt, *args):
        return
