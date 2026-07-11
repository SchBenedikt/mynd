import json
import os
from datetime import datetime

import requests

from .config import OLLAMA, _is_openai, _openai_cfg, C

DATA_DIR = None


def _get_data_dir():
    global DATA_DIR
    if DATA_DIR is None:
        DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    return DATA_DIR


def _load_openai_config():
    """Load OpenAI provider config from ai_config.json, fall back to env vars."""
    ai_cfg_file = os.path.join(_get_data_dir(), 'ai_config.json')
    if os.path.exists(ai_cfg_file):
        try:
            fc = json.loads(open(ai_cfg_file, 'r').read())
            if fc.get('provider') == 'openai':
                base = str(fc.get('base_url', '')).rstrip('/')
                key = str(fc.get('api_key', ''))
                return base or 'https://api.openai.com/v1', key
        except:
            pass
    return _openai_cfg()


def chat_with_tools(model, msgs, tools):
    try:
        if _is_openai(model):
            ob, ok = _load_openai_config()[:2]
            if not ob:
                return {"error": "OpenAI-kompatibler Anbieter nicht konfiguriert (base_url fehlt)."}
            body = {"model": model, "messages": msgs, "stream": False}
            if tools:
                body["tools"] = tools
            h = {"Authorization": f"Bearer {ok}", "Content-Type": "application/json"}
            r = requests.post(f"{ob}/v1/chat/completions", json=body, headers=h, timeout=300)
            data = r.json()
            if "choices" in data:
                m = data["choices"][0].get("message", {})
                return {
                    "message": {
                        "role": m.get("role", "assistant"),
                        "content": m.get("content", ""),
                        "tool_calls": m.get("tool_calls"),
                    }
                }
            return {"error": str(data)[:500]}
        body = {"model": model, "messages": msgs, "stream": False}
        if tools:
            body["tools"] = tools
        if model in ("minimax-m2.5:cloud",):
            body.setdefault("options", {})["temperature"] = 0.3
        r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=300)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "Ollama-Timeout – das Modell hat nicht rechtzeitig geantwortet."}
    except requests.exceptions.ConnectionError:
        return {"error": "Ollama nicht erreichbar – bitte prüfe ob 'ollama serve' läuft."}
    except Exception as e:
        return {"error": f"LLM-Fehler: {e}"}


def chat_with_tools_stream(model, msgs, tools):
    """Yields (event_type, text, final_message_or_None).
    event_type is 'content', 'think', or '' (for final/error).
    """
    try:
        if _is_openai(model):
            ob, ok = _load_openai_config()[:2]
            if not ob:
                yield "", "", {"error": "OpenAI-kompatibler Anbieter nicht konfiguriert (base_url fehlt)."}
                return
            body = {"model": model, "messages": msgs, "stream": True}
            if tools:
                body["tools"] = tools
            h = {"Authorization": f"Bearer {ok}", "Content-Type": "application/json"}
            r = requests.post(f"{ob}/v1/chat/completions", json=body, headers=h, timeout=300, stream=True)
            r.raise_for_status()
            full_content = ""
            final_msg = None
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.strip():
                    continue
                if line.startswith('data: '):
                    line = line[6:]
                if line.strip() == '[DONE]':
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                delta_content = delta.get("content", "")
                if delta_content:
                    full_content += delta_content
                    yield "content", delta_content, None
                if choices[0].get("finish_reason"):
                    tool_calls = delta.get("tool_calls")
                    final_msg = {
                        "role": "assistant",
                        "content": full_content,
                        "tool_calls": tool_calls,
                    }
                    yield "", "", final_msg
                    return
            if not final_msg:
                yield "", "", {"error": "Vorzeitiges Ende des Streams"}
            return
        body = {"model": model, "messages": msgs, "stream": True}
        if tools:
            body["tools"] = tools
        if model in ("minimax-m2.5:cloud",):
            body.setdefault("options", {})["temperature"] = 0.3
        r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=300, stream=True)
        if not r.ok:
            import logging as _lg, json as _js
            _lg.error(f"Ollama 400: {r.text[:500]}")
            _lg.error(f"Request msgs: {len(msgs)}, total chars: {sum(len(str(m)) for m in msgs)}")
            _lg.error(f"Tool names: {[t.get('function',{}).get('name','?') for t in (tools or [])]}")
            with open('/tmp/ollama_fail.json', 'w') as _f:
                _f.write(_js.dumps({"model": model, "messages": msgs, "stream": False}, ensure_ascii=False, indent=2))
            import traceback as _tb
            _lg.error(f"Stack:\n{''.join(_tb.format_stack()[-10:])}")
        r.raise_for_status()
        full_content = ""
        full_thinking = ""
        full_tool_calls = None
        final_msg = None
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = chunk.get("message", {})
            think_text = msg.get("thinking", "")
            content_text = msg.get("content", "")
            if think_text:
                full_thinking += think_text
                yield "think", think_text, None
            if content_text:
                full_content += content_text
                yield "content", content_text, None
            if msg.get("tool_calls"):
                full_tool_calls = msg.get("tool_calls")
            if chunk.get("done"):
                final_msg = {
                    "role": "assistant",
                    "content": full_content,
                    "thinking": full_thinking,
                    "tool_calls": full_tool_calls,
                }
                yield "", "", final_msg
                return
        if not final_msg:
            # Return empty content instead of error – gives the model a chance to retry
            yield "", "", {"role": "assistant", "content": full_content or "", "tool_calls": full_tool_calls}
    except requests.exceptions.Timeout:
        yield "", "", {"error": "Ollama-Timeout – das Modell hat nicht rechtzeitig geantwortet."}
    except requests.exceptions.ConnectionError:
        yield "", "", {"error": "Ollama nicht erreichbar – bitte prüfe ob 'ollama serve' läuft."}
    except Exception as e:
        yield "", "", {"error": f"LLM-Fehler: {e}"}


def run_tool_loop(model, user_msg, system_prompt, tools, tool_map, max_rounds=100, history=None):
    msgs = list(history) if history else []
    if msgs and msgs[0].get("role") == "system":
        msgs[0] = {"role": "system", "content": system_prompt}
    else:
        msgs.insert(0, {"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": user_msg})

    for rnd in range(max_rounds):
        resp = chat_with_tools(model, msgs, tools)
        if "error" in resp:
            return f"❌ Modell-Fehler: {resp['error']}", msgs
        if "message" not in resp:
            return f"❌ Ungültige Antwort (kein 'message'): {str(resp)[:500]}", msgs
        msg = resp["message"]

        if not msg.get("tool_calls"):
            msgs.append({"role": "assistant", "content": msg.get("content", "")})
            return msg.get("content", ""), msgs

        content = msg.get("content", "")
        if content.strip():
            print(f"  {C.YELLOW}💬 {content[:500]}{C.RESET}", flush=True)
        msgs.append({
            "role": "assistant",
            "content": content,
            "tool_calls": msg.get("tool_calls"),
        })

        tool_count = len(msg["tool_calls"])
        print(f"  {C.DIM}▸ Runde {rnd+1}/{max_rounds} · {tool_count} Tool(s){C.RESET}", flush=True)

        for tc in msg["tool_calls"]:
            fn = tc["function"]
            name = fn["name"]
            args_raw = fn.get("arguments", {})
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw)
                except:
                    args = {}
            else:
                args = args_raw
            tool_call_id = tc.get("id", "")
            func = tool_map.get(name)
            if func:
                try:
                    t0 = datetime.now()
                    result = func(**args)
                    dt = (datetime.now() - t0).total_seconds()
                except Exception as e:
                    result = f"❌ Fehler: {e}"
                    dt = 0
            else:
                result = f"❌ Unbekanntes Tool: {name}"
                dt = 0
            r_len = len(str(result))
            status = f"{C.GREEN}✓{C.RESET}" if not result.startswith("❌") else f"{C.RED}✗{C.RESET}"
            if name == "think":
                print(f"    {C.DIM}└─ {status} {name}  {dt:.1f}s{C.RESET}", flush=True)
            else:
                a_str = json.dumps(args)[:120]
                print(f"    {status} {C.BOLD}{name}{C.RESET} {C.DIM}{a_str} · {dt:.1f}s · {r_len} Z{C.RESET}", flush=True)
            msgs.append({
                "role": "tool",
                "content": str(result)[:8000],
                "name": name,
                "tool_call_id": tool_call_id,
            })

    msgs.append({
        "role": "user",
        "content": "Du hast das Limit erreicht. Fasse zusammen, was du bisher herausgefunden hast.",
    })
    resp = chat_with_tools(model, msgs, [])
    if "message" in resp:
        return ("⚠️ Max Runden erreicht.\n\n" + resp["message"].get("content", "")), msgs
    return "⚠️ Max Runden erreicht (keine Abschlussantwort).", msgs
