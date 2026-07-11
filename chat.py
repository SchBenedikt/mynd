#!/usr/bin/env python3
"""Nextcloud Chat – Turbo-Modus. Ein PROPFIND, parallele Downloads, sofort chatten."""

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
from requests.auth import HTTPBasicAuth
from rich.markdown import Markdown

from core import (
    BASE,
    CHUNKS,
    CON,
    CORE_MAP,
    CORE_TOOLS,
    EMBS,
    PERMISSION_HELP,
    PLUGIN_DIR,
    PLUGIN_STATE,
    RICH,
    STATE,
    VAULT_FILE,
    C,
    embed,
    run_tool_loop,
    select_model,
    vault_list,
)

# ── Plugin-System ─────────────────────────────────────
PLUGIN_TOOLS, PLUGIN_MAP, PLUGIN_PROMPTS, PLUGIN_LOADED = [], {}, [], []


def _load_plugins():
    tools, tool_map, prompt_extras, loaded = [], {}, [], []
    if not PLUGIN_DIR.exists():
        return tools, tool_map, prompt_extras, loaded

    enabled = {}
    if PLUGIN_STATE.exists():
        try:
            enabled = json.loads(PLUGIN_STATE.read_text())
        except Exception:
            enabled = {}

    for f in sorted(PLUGIN_DIR.glob("*.py")):
        name = f.stem
        if name.startswith('_'):
            continue
        if not enabled.get(name, True):
            loaded.append((name, False))
            continue
        try:
            import importlib.util as _iu
            spec = _iu.spec_from_file_location(name, f)
            mod = _iu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'TOOLS'):
                tools.extend(mod.TOOLS)
            if hasattr(mod, 'TOOL_MAP'):
                tool_map.update(mod.TOOL_MAP)
            if hasattr(mod, 'PROMPT_EXTRA'):
                prompt_extras.append(mod.PROMPT_EXTRA)
            loaded.append((name, True))
        except Exception as e:
            loaded.append((name, f"❌ {e}"))

    return tools, tool_map, prompt_extras, loaded


def _reload_plugins():
    global PLUGIN_TOOLS, PLUGIN_MAP, PLUGIN_PROMPTS, PLUGIN_LOADED
    PLUGIN_TOOLS, PLUGIN_MAP, PLUGIN_PROMPTS, PLUGIN_LOADED = _load_plugins()


_reload_plugins()

TOOLS = CORE_TOOLS + PLUGIN_TOOLS
TOOL_MAP = {**CORE_MAP, **PLUGIN_MAP}


# ── Text-Chunking ─────────────────────────────────────
def chunk_text(text, size=600):
    lines = text.split('\n')
    chunks, buf, buf_len, hs = [], [], 0, []
    for line in lines:
        if line.startswith('#'):
            m = re.match(r'^(#+)\s+(.*)', line)
            if m:
                hs = [h for h in hs if h['level'] < len(m.group(1))]
                hs.append({'level': len(m.group(1)), 'text': m.group(2)})
        buf.append(line)
        buf_len += len(line) + 1
        if buf_len >= size:
            chunks.append({'text': '\n'.join(buf), 'headings': list(hs)})
            oc = size // 5
            while buf_len > oc and buf:
                p = buf.pop(0)
                buf_len -= len(p) + 1
    if buf:
        chunks.append({'text': '\n'.join(buf), 'headings': list(hs)})
    return chunks


# ── Scan + Index ──────────────────────────────────────
def scan_fast(url, user, pw, dav, folders, exts):
    auth = HTTPBasicAuth(user, pw)
    base = url.rstrip('/')
    dav = dav.rstrip('/')
    ns = {'d': 'DAV:'}
    files = []
    for folder in folders:
        f_url = f"{base}{dav}/{folder}"
        print(f"  Scanne {folder}... ", end='', flush=True)
        try:
            r = requests.request("PROPFIND", f_url,
                                 headers={"Depth": "infinity"}, auth=auth, timeout=600)
            if r.status_code not in (207, 200):
                print(f"{C.RED}Status {r.status_code}{C.RESET}")
                continue
        except Exception as e:
            print(f"{C.RED}{e}{C.RESET}")
            continue
        root = ET.fromstring(r.content)
        n = 0
        for resp in root.findall(".//d:response", ns):
            href = resp.find("d:href", ns)
            if href is None:
                continue
            ht = href.text or ''
            if dav not in ht:
                continue
            rel = ht.split(dav + "/", 1)[-1]
            if not rel:
                continue
            prop = resp.find(".//d:propstat/d:prop", ns)
            if prop is None:
                continue
            if prop.find("d:resourcetype/d:collection", ns) is not None:
                continue
            ext_p = Path(rel).suffix.lower()
            if ext_p not in exts:
                continue
            s = prop.find("d:getcontentlength", ns)
            e = prop.find("d:getetag", ns)
            files.append(dict(
                rel=rel, url=f"{base}{ht}",
                size=int(s.text or 0) if s else 0,
                etag=(e.text or '').strip('"'), ext=ext_p,
            ))
            n += 1
        print(f"{C.GREEN}{n} Dateien{C.RESET}")
    return files


def _process_file(args):
    url, user, pw, rel, ext = args
    try:
        r = requests.get(url, auth=HTTPBasicAuth(user, pw), timeout=120)
        r.raise_for_status()
        data = r.content
        sha = hashlib.sha256(data).hexdigest()
        if ext in ('.md', '.txt'):
            text = data.decode('utf-8', errors='replace')
        elif ext == '.docx':
            try:
                import io

                from docx import Document
                doc = Document(io.BytesIO(data))
                lines = []
                for p in doc.paragraphs:
                    s = p.style.name.lower() if p.style else ''
                    if 'heading' in s:
                        lvl = ''.join(filter(str.isdigit, s)) or '1'
                        lines.append(f"{'#' * int(lvl)} {p.text}")
                    else:
                        lines.append(p.text)
                text = '\n\n'.join(lines)
            except Exception as e:
                text = f"*(DOCX error: {e})*\n\n{rel}"
        elif ext == '.pdf':
            text = f"*(PDF: {rel})*"
            try:
                import tempfile

                from docling.document_converter import DocumentConverter
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(data)
                    tmp = f.name
                try:
                    text = DocumentConverter().convert(tmp).document.export_to_markdown()
                finally:
                    os.unlink(tmp)
            except Exception as e:
                text = f"*(PDF error: {e})*\n\n{rel}"
        else:
            text = data.decode('utf-8', errors='replace')
        return (rel, sha, text, None)
    except Exception as e:
        return (rel, None, None, str(e))


# ── Main ──────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--force', action='store_true', help='Alle Dateien neu laden (ignoriert Cache)')
    p.add_argument('--rescan', action='store_true', help='Neu scannen, nur neue/geänderte laden')
    p.add_argument('--rounds', type=int, default=100, help='Max Tool-Runden (default: 100)')
    p.add_argument('--model', type=str, default='', help='LLM-Modell (z.B. gemma3:12b, gpt-4o-mini; überspringt Auswahl)')
    p.add_argument('--permission', type=str, default='auto', choices=['auto', 'semi', 'ask'],
                   help='Bash-Berechtigung')
    args = p.parse_args()

    if not (BASE / '.env').exists():
        print(f"{C.RED}❌ .env nicht gefunden{C.RESET}")
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv(BASE / '.env')
    BASE.joinpath('data').mkdir(parents=True, exist_ok=True)

    global PERMISSION_MODE
    PERMISSION_MODE = args.permission

    def nc_env(k):
        return os.environ[k]
    nc_dav = nc_env('NEXTCLOUD_WEBDAV_PATH')
    folders = [f.strip() for f in nc_env('SYNC_FOLDERS').split(',')]
    exts = set(nc_env('SYNC_FILE_EXTENSIONS').split(','))

    state = {}
    if STATE.exists():
        state = json.loads(STATE.read_text())

    if args.rescan or args.force or not state:
        print(f"{C.YELLOW}📡 Scan (Depth:infinity)...{C.RESET}", flush=True)
        all_files = scan_fast(nc_env('NEXTCLOUD_URL'), nc_env('NEXTCLOUD_USERNAME'),
                              nc_env('NEXTCLOUD_PASSWORD'), nc_dav, folders, exts)
        print(f"  {C.GREEN}📁 {len(all_files)} Dateien gesamt{C.RESET}", flush=True)
        if args.force:
            todo = list(all_files)
        else:
            todo = [f for f in all_files
                    if f['rel'] not in state or state[f['rel']].get('etag') != f['etag']]
    else:
        all_files = [dict(rel=k, etag=v.get('etag', ''), size=v.get('size', 0),
                          ext=Path(k).suffix.lower(), url='')
                     for k, v in state.items()]
        todo = []

    print(f"  {C.GREEN}📁 {len(all_files)} Dateien bekannt{C.RESET}", flush=True)

    if not todo:
        print(f"  {C.GREEN}✅ Alles aktuell{C.RESET}", flush=True)
    else:
        print(f"  {C.YELLOW}📥 {len(todo)} Dateien neu/geändert, lade parallel...{C.RESET}", flush=True)
        max_workers = 20
        all_chunks = []
        all_embs = np.array([]).reshape(0, 0)
        if CHUNKS.exists() and EMBS.exists():
            all_chunks = json.loads(CHUNKS.read_text())
            all_embs = np.load(EMBS)

        batch_texts = []
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_process_file, (
                f['url'], nc_env('NEXTCLOUD_USERNAME'), nc_env('NEXTCLOUD_PASSWORD'),
                f['rel'], f['ext']
            )): f for f in todo}
            for fut in as_completed(futures):
                done += 1
                rel, sha, text, err = fut.result()
                if err:
                    logger = __import__('logging').getLogger(__name__)
                    logger.error(f"Fehler {rel}: {err}")
                elif sha:
                    for f in todo:
                        if f['rel'] == rel:
                            state[rel] = {
                                'etag': f['etag'], 'size': f['size'], 'hash': sha,
                                'indexed_at': datetime.now().isoformat(),
                            }
                            break
                    cs = chunk_text(text)
                    for c in cs:
                        batch_texts.append(c['text'])
                        all_chunks.append({
                            'text': c['text'], 'source': rel,
                            'headings': c.get('headings', []),
                        })
                    if len(batch_texts) >= 10:
                        e = embed(batch_texts)
                        all_embs = np.vstack([all_embs, e]) if all_embs.size else e
                        batch_texts.clear()
                        CHUNKS.write_text(json.dumps(all_chunks, indent=2))
                        np.save(str(EMBS), all_embs)
                        STATE.write_text(json.dumps(state, indent=2))
                if done % 50 == 0:
                    print(f"    {done}/{len(todo)} ({len(all_chunks)} Chunks)", end='\r', flush=True)

        if batch_texts:
            e = embed(batch_texts)
            all_embs = np.vstack([all_embs, e]) if all_embs.size else e

        CHUNKS.write_text(json.dumps(all_chunks, indent=2))
        np.save(str(EMBS), all_embs)
        STATE.write_text(json.dumps(state, indent=2))
        print(f"\n  {C.GREEN}✅ Index: {len(all_chunks)} Chunks von {len(state)} Dateien{C.RESET}", flush=True)

    # ── Modell ─────────────────────────────────────────
    model_name = select_model(args.model)
    if model_name:
        os.environ.setdefault("OLLAMA_MODEL", model_name)
        print(f"  {C.GREEN}🧠 {model_name}{C.RESET}", flush=True)

    # ── Chat ───────────────────────────────────────────
    chunks, embs = [], np.array([]).reshape(0, 0)
    if CHUNKS.exists() and EMBS.exists():
        chunks = json.loads(CHUNKS.read_text())
        embs = np.load(EMBS)

    sep = f"  {C.DIM}──────────────────────────────────{C.RESET}"

    def fmt_src(srcs_dict):
        items = sorted(srcs_dict, key=lambda x: -srcs_dict[x])[:8]
        return '  ' + '\n  '.join(f"{C.DIM}📄 {s}{C.RESET}" for s in items) if items else ""

    def show_banner():
        os.system('clear' if os.name == 'posix' else 'cls')
        w = 50
        p_icon = {"auto": "🤖", "semi": "⚠️", "ask": "🔒"}[PERMISSION_MODE]
        mem_count = 0
        mem_f = BASE / 'data' / 'memory.json'
        if mem_f.exists():
            try:
                mem_count = len(json.loads(mem_f.read_text()))
            except Exception:
                pass
        print(
            f"{C.CYAN}{C.BOLD}╭{'─'*w}╮\n"
            f"│  📖  Nextcloud Chat{' ' * (w - 22)}│\n"
            f"│{' ' * (w + 2)}│\n"
            f"│  {f'📚 {len(chunks)} Chunks · {len(all_files)} Dateien':{w}} │\n"
            f"│  {f'🧠 {model_name}':{w}} │\n"
            f"│  {f'{p_icon} Bash: {PERMISSION_MODE.upper()}':{w}} │\n"
            f"│  {f'🧠 {mem_count} Memory · {"✓" if VAULT_FILE.exists() and VAULT_FILE.stat().st_size > 10 else "✗ leer"} Vault':{w}} │\n"
            f"╰{'─'*w}╯{C.RESET}\n"
            f"{C.DIM}/bye  /help  /memory  /model  /permission  /plugins  /status  /top N  /vault{C.RESET}\n"
        )

    show_banner()
    top_k = 15
    chat_history = None

    memory_block = ""
    mem_file = BASE / 'data' / 'memory.json'
    if mem_file.exists():
        try:
            mem = json.loads(mem_file.read_text())
            if mem:
                items = [f"  {k}: {v}" for k, v in sorted(mem.items())]
                memory_block = "## Gespeichertes Wissen (Memory)\n" + '\n'.join(items) + "\n\n"
        except Exception:
            pass

    while True:
        try:
            ts = datetime.now().strftime("%H:%M")
            prompt_str = f"\n{C.CYAN}{C.BOLD}┃ {ts} {C.RESET}{C.BOLD}Du{C.RESET} "
            if RICH:
                from rich.prompt import Prompt
                q = Prompt.ask(prompt_str).strip()
            else:
                q = input(prompt_str).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C.YELLOW}Tschüss!{C.RESET}")
            break
        if not q:
            continue

        cmd = q.lower()
        if cmd in ('/bye', '/exit', '/quit'):
            print(f"\n{C.YELLOW}Tschüss!{C.RESET}")
            break

        if cmd == '/status':
            n = sum(1 for v in state.values() if v.get('indexed_at'))
            print(
                f"{C.CYAN}  Status:{C.RESET}\n"
                f"    Dateien:   {n}/{len(all_files)} indexiert\n"
                f"    Chunks:    {len(chunks)}\n"
                f"    TOP-K:     {top_k}\n"
                f"    Modell:    {model_name}\n"
                f"    Vault:     {VAULT_FILE.stat().st_size if VAULT_FILE.exists() else 0} Bytes"
            )
            continue

        if cmd == '/vault':
            v = vault_list()
            if v and v != "(leer)":
                print(f"  {C.CYAN}Vault:{C.RESET}{v}")
            else:
                print(f"  {C.YELLOW}Vault ist leer.{C.RESET}")
            continue

        if cmd.startswith('/top '):
            try:
                top_k = int(cmd.split('/top ')[1])
                print(f"  {C.GREEN}TOP-K → {top_k}{C.RESET}")
            except Exception:
                print(f"  {C.RED}Ungültige Zahl{C.RESET}")
            continue

        if cmd == '/model':
            new = select_model()
            if new and new != model_name:
                model_name = new
                chat_history = None
                show_banner()
            continue

        if cmd == '/memory':
            mem_file2 = BASE / 'data' / 'memory.json'
            if mem_file2.exists():
                try:
                    mem = json.loads(mem_file2.read_text())
                    if mem:
                        print(f"  {C.CYAN}Gespeichertes Wissen:{C.RESET}")
                        for k, v in sorted(mem.items()):
                            print(f"    {C.BOLD}{k}{C.RESET}: {v[:100]}{'…' if len(v) > 100 else ''}")
                    else:
                        print(f"  {C.YELLOW}Memory ist leer.{C.RESET}")
                except Exception:
                    print(f"  {C.RED}Fehler beim Lesen.{C.RESET}")
            else:
                print(f"  {C.YELLOW}Keine Memory-Datei.{C.RESET}")
            continue

        if cmd == '/plugins':
            lines = [f"  {C.CYAN}Plugins:{C.RESET}"]
            for name, status in PLUGIN_LOADED:
                if status is True:
                    lines.append(f"    {C.GREEN}✓{C.RESET} {name}")
                elif status is False:
                    lines.append(f"    {C.DIM}⊘{C.RESET} {name} (deaktiviert)")
                else:
                    lines.append(f"    {C.RED}✗{C.RESET} {name}: {status}")
            print('\n'.join(lines) if PLUGIN_LOADED else f"  {C.YELLOW}Keine Plugins.{C.RESET}")
            continue

        if cmd in ('/permission', '/perm'):
            print(f"  {C.CYAN}Bash-Berechtigung:{C.RESET}")
            for k, v in PERMISSION_HELP.items():
                marker = f"{C.GREEN}→{C.RESET}" if k == PERMISSION_MODE else " "
                print(f"    {marker} {C.BOLD}{k}{C.RESET} – {v}")
            try:
                choice = input(f"  {C.CYAN}Modus wählen{C.RESET} (auto/semi/ask): ").strip().lower()
                if choice in PERMISSION_HELP:
                    PERMISSION_MODE = choice
                    show_banner()
                else:
                    print(f"  {C.RED}Ungültig. Bleibt: {PERMISSION_MODE}{C.RESET}")
            except EOFError:
                pass
            continue

        if cmd == '/help':
            print(
                f"{C.CYAN}  Befehle:{C.RESET}\n"
                f"    {C.GREEN}/bye{C.RESET}     Beenden\n"
                f"    {C.GREEN}/exit{C.RESET}    Beenden\n"
                f"    {C.GREEN}/help{C.RESET}    Diese Hilfe\n"
                f"    {C.GREEN}/memory{C.RESET}  Gespeichertes Wissen anzeigen\n"
                f"    {C.GREEN}/model{C.RESET}   LLM-Modell wechseln\n"
                f"    {C.GREEN}/perm{C.RESET}    Bash-Berechtigung ändern (auto/semi/ask)\n"
                f"    {C.GREEN}/plugins{C.RESET} Geladene Plugins anzeigen\n"
                f"    {C.GREEN}/status{C.RESET}  Index-Status anzeigen\n"
                f"    {C.GREEN}/top N{C.RESET}   Suchergebnisse (TOP-K) ändern\n"
                f"    {C.GREEN}/vault{C.RESET}   Gespeicherte Zugangsdaten anzeigen"
            )
            continue

        if len(embs) == 0:
            print(f"  {C.YELLOW}Keine Daten. Starte mit --force{C.RESET}")
            continue

        print(f"  {C.DIM}Suche...{C.RESET}", end='', flush=True)
        q_emb = embed([q])[0]
        scores = np.array([
            float(np.dot(q_emb, e) / (np.linalg.norm(q_emb) * np.linalg.norm(e) + 1e-10))
            for e in embs
        ])
        top_idx = np.argsort(scores)[-top_k:][::-1]
        found = [(chunks[i], scores[i]) for i in top_idx if scores[i] > 0.15]

        if not found:
            print(f"\r  {C.YELLOW}Keine relevanten Dokumente gefunden.{C.RESET}")
            ctx_block = ""
            src_list = ""
        else:
            print(f"\r  {C.GREEN}✓ {len(found)} Quellen{C.RESET}")
            ctx, srcs = [], {}
            for i, (c, sc) in enumerate(found):
                srcs[c['source']] = srcs.get(c['source'], 0) + 1
                hd = ' > '.join(h['text'] for h in c.get('headings', []))
                ctx.append(f"[{i+1}] {c['source']}" + (f" / {hd}" if hd else ""))
                ctx.append(c['text'][:1500])
            src_list = ', '.join(sorted(srcs, key=lambda x: -srcs[x])[:8])
            ctx_block = "## Kontext\n" + '\n\n'.join(ctx)

        plugin_extra = ''.join(PLUGIN_PROMPTS)
        system = (
            "Du bist ein KI-Assistent mit Zugriff auf die Nextcloud-Dokumente des Users.\n"
            "Du hast KERN-WERKZEUGE:\n"
            f"- **execute_bash**: Bash-Befehle ausführen (Modus: {PERMISSION_MODE.upper()} – "
            f"{'alle erlaubt' if PERMISSION_MODE == 'auto' else 'kritische Befehle werden nachgefragt' if PERMISSION_MODE == 'semi' else 'alle werden nachgefragt'})\n"
            "- **execute_ssh**: Befehl per SSH auf Remote-Host (Vault: vm/<profil>/ip, user, password, key)\n"
            "- **http_request**: HTTP-Request an JEDE REST-API. auth_user + auth_pass für Basic Auth (UTF-8-sicher). Self-Signed-Certs automatisch akzeptiert.\n"
            "- **search_documents**: Indexierte Dokumente semantisch durchsuchen\n"
            "- **read_local_file / write_local_file**: Lokale Dateien lesen/schreiben\n"
            "- **think**: IMMER ZUERST aufrufen. Plane dein Vorgehen.\n"
            "- **vault_get / vault_set / vault_list / vault_delete**: Zugangsdaten speichern/lesen\n"
            "- **prompt_user**: User interaktiv nach Eingabe fragen (wenn vault_get nichts findet)\n"
            "- **memory_get / memory_set / memory_delete**: Dauerhaftes Gedächtnis über Chats hinweg (z.B. user/name, network/ip_range)\n"
            "GELADENE PLUGINS können weitere Tools bereitstellen (z.B. Nextcloud, Email).\n\n"
            "WICHTIGE REGELN:\n"
            "- Credentials IMMER per vault_get() abrufen. NIEMALS aus Nachrichten kopieren (Umlaute werden zerstört).\n"
            "- vault_get liefert nichts? → prompt_user() + vault_set().\n"
            "- Die Dokumente unten sind nur KONTEXT – nicht die User-Nachricht.\n"
            "- http_request schlägt fehl? → execute_bash mit Python/requests (verify=False).\n"
            "- Remote-Befehle? → execute_ssh (profile=..., Credentials aus Vault vm/<profil>/).\n"
            "- API-Endpunkte unbekannt? → read_local_file('data/api_refs.json').\n"
            "- Nach 3 Fehlschlägen: komplett andere Strategie.\n\n"
            "BEISPIEL: 'TrueNAS-Update?' → vault_get(truenas/*) → http_request mit auth_user/auth_pass.\n\n"
            "ENTSCHEIDUNGS-BAUM:\n"
            "1. **DENKE** → think()\n"
            "2. **WISSEN** → search_documents\n"
            "3. **AKTION** → Vault → prompt_user (bei Fehlen) → vault_set → http_request / execute_ssh. API unbekannt? → api_refs.json.\n"
            "4. **MERKEN** → User sagt etwas Persönliches? → memory_set() speichern.\n"
            "5. **ANTWORTEN**: Deutsch. Quelle nennen.\n\n"
            f"DATUM AKTUELL: 28.06.2026. Nächste Woche = KW 27 (29.06.–05.07.).\n\n"
            f"{plugin_extra}"
            f"{memory_block}"
            "Antworte basierend auf dem Kontext. Zitiere Quellen mit [1],[2]...\n"
            f"Verfügbare Quellen: {src_list}"
        )

        print(f"  {C.DIM}LLM denkt...{C.RESET}", end='', flush=True)
        try:
            antwort, chat_history = run_tool_loop(
                model_name, q, system + "\n\n" + ctx_block,
                TOOLS, TOOL_MAP, max_rounds=args.rounds, history=chat_history,
            )
            print(f"\r{sep}", flush=True)
            if RICH:
                CON.print(Markdown(str(antwort)))
            else:
                print(f"{C.GREEN}{antwort}{C.RESET}")
            if src_list:
                print(f"{C.DIM}  📎 {src_list}{C.RESET}")
        except KeyError:
            print(f"\r  {C.RED}✗ Modell ohne Tool-Support. /model zum Wechseln{C.RESET}")
        except Exception as e:
            print(f"\r  {C.RED}✗ {e}{C.RESET}")


if __name__ == '__main__':
    main()
