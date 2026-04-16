import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

INTENT_KEYWORDS = [
    "preciso de", "recomenda", "indicação", "orçamento", "custo",
    "barato", "melhor app", "onde encontro", "contratar", "serviço",
    "indique", "ajuda com", "procuro"
]

def calcular_score(texto: str, horas_atras: float) -> int:
    texto_lower = texto.lower()
    kw_matches = sum(1 for kw in INTENT_KEYWORDS if kw in texto_lower)
    score_palavras = min(kw_matches * 15, 45)
    score_recencia = min(25, max(0, 25 - horas_atras))
    return min(score_palavras + score_recencia + 30, 100)

def buscar_reddit(subreddit: str, termo: str, limite: int = 15):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": termo, "sort": "new", "limit": limite, "restrict_sr": "on"}
    headers = {"User-Agent": "RadarLeads/1.0 (local)"}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.raise_for_status()
        dados = res.json().get("data", {}).get("children", [])
        resultados = []
        for p in dados:
            d = p.get("data", {})
            texto = f"{d.get('title', '')} {d.get('selftext', '')}".strip()
            if texto:
                criado_em = d.get("created_utc", 0)
                horas = (datetime.now(timezone.utc).timestamp() - criado_em) / 3600
                score = calcular_score(texto, horas)
                resultados.append({
                    "platform": "reddit",
                    "author": d.get("author", "anônimo"),
                    "post_url": f"https://reddit.com{d.get('permalink')}",
                    "raw_text": texto,
                    "intent_score": score,
                    "status": "novo",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
        return resultados
    except Exception as e:
        print(f"⚠️ Erro Reddit: {e}")
        return []

def salvar_no_supabase(leads):
    if not leads:
        return 0
    try:
        # Upsert evita duplicatas pelo post_url
        res = supabase.table("leads").upsert(leads, on_conflict="post_url").execute()
        return len(res.data) if res.data else 0
    except Exception as e:
        print(f"⚠️ Erro ao salvar: {e}")
        return 0

def main():
    print("🔍 Varrendo oportunidades...")
    buscas = [
        ("brasil", "recomenda app"),
        ("empreendedores", "preciso de"),
        ("freelanceBR", "procurando"),
    ]
    
    todos_leads = []
    for sub, termo in buscas:
        todos_leads += buscar_reddit(sub, termo)
    
    if not todos_leads:
        print("✅ Nenhum lead novo encontrado desta vez.")
        return

    salvos = salvar_no_supabase(todos_leads)
    print(f"📥 {salvos} leads salvos no Supabase.")
    print("👉 Abra seu painel para ver e agir.")

if __name__ == "__main__":
    main()
