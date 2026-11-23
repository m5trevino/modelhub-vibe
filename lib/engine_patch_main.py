from pathlib import Path
p = Path("/root/hetzner/ai-engine/app/main.py")
s = p.read_text()
if "# MODELHUB INTEGRITY" in s:
    print("main already patched")
    raise SystemExit(0)
old = '''        "integrity": {
            "groq": len(GroqPool.deck),
            "opencode-go": len(OpencodeGoPool.deck),
            "openrouter": len(OpenrouterPool.deck),
            "ollama": len(OllamaPool.deck),
            "hetzner": len(HetznerPool.deck),
            "merge": len(MergePool.deck),
            "novita": len(NovitaPool.deck),
            "xkiro": len(XkiroPool.deck),
            "explabs": len(ExplabsPool.deck),
            "mistral": len(MistralPool.deck),
        },'''
new = '''        # MODELHUB INTEGRITY
        "integrity": {
            "groq": len(GroqPool.deck),
            "openrouter": len(OpenrouterPool.deck),
            "ollama": len(OllamaPool.deck),
            "hetzner": len(HetznerPool.deck),
            "merge": len(MergePool.deck),
            "novita": len(NovitaPool.deck),
            "xkiro": len(XkiroPool.deck),
        },'''
if old not in s:
    print("integrity anchor missing")
    raise SystemExit(2)
s = s.replace(old, new, 1)
tmp = p.with_suffix(".py.tmp")
tmp.write_text(s)
tmp.replace(p)
print("main patched")
