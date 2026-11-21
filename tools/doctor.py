#!/usr/bin/env python3
"""302API 接入自检：一条命令确认 Key、地址、网络和可用模型，并给出可直接复制的配置。

只用 Python 标准库（3.10+），不需要安装依赖。默认只调用不产生费用的接口：
  - GET /v1/models            （需要 Key，列出当前 Key 可用的模型）
  - GET /api/public/models    （公开价格目录，不需要 Key）
加 --chat MODEL_ID 时会额外发一次很短的对话请求，**会产生少量费用**。

用法：
  python3 tools/doctor.py
  python3 tools/doctor.py --chat gpt-6-luna
  python3 tools/doctor.py --json            # 机器可读输出，便于在 CI 或工单里附上
Key 从环境变量 API_302API_KEY 读取，不会打印出来。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.302api.com/v1"
CATALOG_URL = "https://dashboard.302api.com/api/public/models"
UA = "302api-developer-kit-doctor/1.0"


def tls_context() -> ssl.SSLContext:
    """系统证书优先；装了 certifi 时一并加载（macOS 上 python.org 安装的 Python 默认没有根证书）。"""
    ctx = ssl.create_default_context()
    try:
        import certifi  # type: ignore
        ctx.load_verify_locations(certifi.where())
    except (ImportError, OSError):
        pass
    return ctx


SSL_HINT = ("证书校验失败。macOS 上用 python.org 安装的 Python，请运行“应用程序/Python 3.x/Install Certificates.command”，"
            "或执行 python3 -m pip install certifi 后重试；公司网络如有 HTTPS 代理，需要导入代理的根证书")
PROVIDERS = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "deepseek": "DeepSeek"}


class Report:
    def __init__(self, as_json: bool):
        self.as_json = as_json
        self.checks: list[dict] = []
        self.data: dict = {}

    def add(self, name: str, ok: bool | None, detail: str, hint: str = "") -> None:
        self.checks.append({"check": name, "ok": ok, "detail": detail, "hint": hint})
        if not self.as_json:
            mark = "✓" if ok else ("·" if ok is None else "✗")
            print(f" {mark} {name}：{detail}")
            if hint and not ok:
                print(f"   → {hint}")


def request(url: str, key: str | None = None, body: dict | None = None, timeout: float = 20):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    data = None
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=tls_context()) as resp:
            raw = resp.read()
            return resp.status, dict(resp.headers), raw, time.monotonic() - started
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers or {}), err.read(), time.monotonic() - started


def error_message(raw: bytes) -> str:
    try:
        err = json.loads(raw).get("error") or {}
        return f"{err.get('code') or err.get('type') or ''} {err.get('message') or ''}".strip()
    except (ValueError, AttributeError):
        return raw[:200].decode("utf-8", "replace")


def check_key(r: Report) -> str | None:
    key = os.environ.get("API_302API_KEY", "").strip()
    if not key:
        r.add("API Key", False, "未设置环境变量 API_302API_KEY",
              "在控制台 https://dashboard.302api.com 创建 Key，然后 export API_302API_KEY=...（见 docs/quick-start.md）")
        return None
    if not key.startswith("sk-302api-"):
        r.add("API Key", False, "格式不像本站 Key（本站 Key 以 sk-302api- 开头）", "确认没有粘贴成其他平台的 Key")
        return key
    if len(key) != 53:
        r.add("API Key", False, f"长度 {len(key)}，本站 Key 为 53 位", "可能复制不完整或多了空格")
        return key
    r.add("API Key", True, "已设置，格式正确（不显示内容）")
    return key


def check_base(r: Report) -> str:
    base = os.environ.get("API_302API_BASE_URL", DEFAULT_BASE).strip().rstrip("/")
    path = urllib.parse.urlsplit(base).path
    problems = []
    if path.endswith("/v1/v1"):
        problems.append("地址里重复了 /v1")
    elif not path.endswith("/v1"):
        problems.append("OpenAI 兼容地址应以 /v1 结尾")
    if any(p in path for p in ("/chat/completions", "/responses", "/messages")):
        problems.append("Base URL 只填到 /v1，不要包含具体接口路径")
    if problems:
        r.add("Base URL", False, f"{base}（{'；'.join(problems)}）", f"改为 {DEFAULT_BASE}")
    else:
        r.add("Base URL", True, base)
    return base


def check_network(r: Report, base: str) -> bool:
    host = urllib.parse.urlsplit(base).hostname or "api.302api.com"
    try:
        t0 = time.monotonic()
        addr = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)[0][4][0]
        t1 = time.monotonic()
        with socket.create_connection((host, 443), timeout=8) as sock:
            t2 = time.monotonic()
            with tls_context().wrap_socket(sock, server_hostname=host):
                t3 = time.monotonic()
        r.data["network"] = {"host": host, "dns_ms": round((t1 - t0) * 1000), "tcp_ms": round((t2 - t1) * 1000),
                             "tls_ms": round((t3 - t2) * 1000)}
        r.add("网络", True, f"{host}（{addr}）DNS {r.data['network']['dns_ms']} ms · TCP {r.data['network']['tcp_ms']} ms · TLS {r.data['network']['tls_ms']} ms")
        return True
    except ssl.SSLCertVerificationError:
        r.add("网络", False, f"能连上 {host}，但本机无法校验 HTTPS 证书", SSL_HINT)
        return False
    except (OSError, ssl.SSLError) as err:
        r.add("网络", False, f"无法连接 {host}:443（{err.__class__.__name__}）",
              "检查代理、防火墙或公司网络是否拦截；也可以先打开 https://302api.com/status/ 看服务状态")
        return False


def load_catalog() -> dict:
    try:
        status, _, raw, _ = request(CATALOG_URL, timeout=15)
        if status == 200:
            return {m["model_id"]: m for m in json.loads(raw).get("items", [])}
    except (OSError, ValueError):
        pass
    return {}


def check_models(r: Report, base: str, key: str, catalog: dict) -> list[str]:
    status, headers, raw, took = request(f"{base}/models", key=key)
    if status != 200:
        hint = {401: "Key 无效、已停用或复制不完整：到控制台确认 Key 状态",
                402: "余额不足：先在控制台充值（注册赠送的额度用完后需要充值）",
                403: "该 Key 没有可用模型或被限制：检查 Key 的模型范围"}.get(status, "附上请求编号和时间联系支持")
        r.add("鉴权与模型列表", False, f"HTTP {status} {error_message(raw)}", hint)
        return []
    ids = [m["id"] for m in json.loads(raw).get("data", [])]
    r.add("鉴权与模型列表", True, f"Key 可用，可调用 {len(ids)} 个模型（{round(took * 1000)} ms）")
    r.data["models"] = []
    groups: dict[str, list[str]] = {}
    for mid in ids:
        info = catalog.get(mid, {})
        provider = PROVIDERS.get(info.get("price_provider", ""), info.get("price_provider") or "其他")
        kind = "生图" if info.get("model_type") == "image" else "对话"
        price = ""
        if kind == "对话" and info.get("customer_input_price") is not None:
            price = f"输入 ${float(info['customer_input_price']):g} / 输出 ${float(info['customer_output_price']):g}（每百万 Token）"
        groups.setdefault(provider, []).append(f"{mid}  [{kind}] {price}".rstrip())
        r.data["models"].append({"id": mid, "provider": provider, "type": kind,
                                 "input_usd_per_m": info.get("customer_input_price"),
                                 "output_usd_per_m": info.get("customer_output_price")})
    if not r.as_json:
        for provider in sorted(groups):
            print(f"     {provider}")
            for line in sorted(groups[provider]):
                print(f"       - {line}")
    return ids


def check_chat(r: Report, base: str, key: str, model: str) -> None:
    body = {"model": model, "messages": [{"role": "user", "content": "只回复：OK"}], "max_tokens": 16}
    status, headers, raw, took = request(f"{base}/chat/completions", key=key, body=body, timeout=60)
    rid = next((v for k, v in headers.items() if k.lower() == "x-302api-request-id"), "")
    if status != 200:
        r.add("对话测试", False, f"{model} → HTTP {status} {error_message(raw)}（请求编号 {rid or '无'}）",
              "确认模型 ID 与上面的列表完全一致；把请求编号发给支持可以更快排查")
        return
    data = json.loads(raw)
    usage = data.get("usage") or {}
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    r.data["chat"] = {"model": data.get("model", model), "latency_ms": round(took * 1000), "usage": usage, "request_id": rid}
    r.add("对话测试", True, f"{model} 回复 {text.strip()[:20]!r}，耗时 {round(took * 1000)} ms，"
                            f"输入 {usage.get('prompt_tokens')} / 输出 {usage.get('completion_tokens')} Token，请求编号 {rid}")
    if not r.as_json:
        print("   → 这次调用会出现在控制台“调用记录”里，可以用请求编号逐条核对扣费。")


def snippets(base: str, models: list[str]) -> None:
    chat = next((m for m in ("gpt-6-luna", "claude-haiku-5-5", "gemini-3.8-flash") if m in models), models[0] if models else "MODEL_ID")
    claude = next((m for m in ("claude-sonnet-5-5", "claude-haiku-5-5") if m in models), "claude-sonnet-5-5")
    root = base[: -len("/v1")] if base.endswith("/v1") else base
    print(f"""
可直接复制的配置
  # OpenAI SDK / Cherry Studio / Cline（OpenAI Compatible）
  export API_302API_BASE_URL='{base}'
  export MODEL_ID='{chat}'

  # Anthropic SDK / Claude Code（原生接口，地址不带 /v1）
  export ANTHROPIC_BASE_URL='{root}'
  export ANTHROPIC_MODEL_ID='{claude}'

  # Codex CLI（~/.codex/config.toml，Key 放在环境变量 API302_KEY）
  [model_providers.302api]
  name = "302API"
  base_url = "{base}"
  env_key = "API302_KEY"
  wire_api = "responses"
  supports_websockets = false""")


def main() -> int:
    parser = argparse.ArgumentParser(description="302API 接入自检")
    parser.add_argument("--chat", metavar="MODEL_ID", help="额外发一次很短的对话请求（会产生少量费用）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    r = Report(args.json)
    if not args.json:
        print("302API 接入自检\n")
    key = check_key(r)
    base = check_base(r)
    online = check_network(r, base)
    models: list[str] = []
    if key and online:
        models = check_models(r, base, key, load_catalog())
        if args.chat and models:
            check_chat(r, base, key, args.chat)
    failed = [c for c in r.checks if c["ok"] is False]
    if args.json:
        print(json.dumps({"ok": not failed, "checks": r.checks, **r.data}, ensure_ascii=False, indent=2))
    else:
        if not failed and models:
            snippets(base, models)
        print("\n结论：" + ("全部通过，可以开始调用。" if not failed else f"{len(failed)} 项需要处理，见上方 → 提示。"))
        if not args.chat and not failed:
            print("想确认真实对话链路，可以运行：python3 tools/doctor.py --chat MODEL_ID（会产生少量费用）")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
