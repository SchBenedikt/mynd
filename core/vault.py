import json
from .config import VAULT_FILE, C

def vault_get(key=""):
    try:
        v = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        if not key:
            # No key → group by prefix
            groups = {}
            for k in sorted(v):
                prefix = k.split('/')[0]
                groups.setdefault(prefix, []).append(k)
            lines = ["Verfügbare Vault-Keys:"]
            for g in sorted(groups):
                lines.append(f"  {g}:")
                for k in groups[g]:
                    val = str(v[k])
                    if any(w in k.lower() for w in ('password', 'key', 'token', 'secret')):
                        val = val[:4] + '…' if len(val) > 4 else '***'
                    else:
                        val = val[:60]
                    lines.append(f"    {k}: {val}")
            return '\n'.join(lines)
        return v.get(key, "")
    except:
        return "❌ Fehler"

def vault_set(key, value):
    try:
        v = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        v[key] = value
        VAULT_FILE.write_text(json.dumps(v, indent=2))
        return f"✅ `{key}` gespeichert"
    except Exception as e:
        return f"❌ {e}"

def vault_delete(key):
    try:
        v = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        if key in v:
            del v[key]
            VAULT_FILE.write_text(json.dumps(v, indent=2))
            return f"🗑 `{key}` gelöscht"
        return f"❌ `{key}` nicht gefunden"
    except Exception as e:
        return f"❌ {e}"

def vault_list(group=""):
    try:
        v = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        if not v:
            return "(leer)"
        groups = {}
        for k in sorted(v):
            if "/" in k:
                g, _, rest = k.partition("/")
                groups.setdefault(g, {})[rest or k] = v[k]
            else:
                groups.setdefault("_all", {})[k] = v[k]
        if group:
            g = groups.get(group, {})
            return '\n'.join(f"  {k}: {str(g[k])[:60]}" for k in g) if g else f"(Gruppe '{group}' leer)"
        lines = []
        for g in sorted(groups):
            lines.append(f"\n  {C.CYAN}{g}{C.RESET}")
            for k in sorted(groups[g]):
                vv = str(groups[g][k])
                lines.append(f"    {k}: {vv[:50]}{'…' if len(vv) > 50 else ''}")
        return '\n'.join(lines) if lines else "(leer)"
    except:
        return "❌ Fehler"

def _vault_get(key):
    v = vault_get(key)
    return v if v != "❌ Nicht gefunden" else ""
