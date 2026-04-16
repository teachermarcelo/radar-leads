import os
import requests
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

INTENT_KEYWORDS = [
    "preciso de", "recomenda", "indicação", "orçamento", "custo",
    "barato", "melhor app", "onde encontro", "contratar", "serviço",
    "indique", "ajuda com", "procuro", "sugestão"
]

def calcular_score(texto: str, horas_atras: float) -> int:
    texto_lower = texto.lower()
    kw_matches = sum(1 for kw in INTENT_KEYWORDS if kw in texto_lower)
    score_palavras = min(kw_matches * 15, 45)
    score_recencia = min(25, max(0, 25 - horas_atras))
    return min(score_palavras + score_recencia + 30, 100)

def buscar_reddit(subreddit: str, termo: str, limite: int = 20):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    # t=week garante posts da última semana
    params = {
        "q": termo, 
        "sort": "new", 
        "time": "week",  # ✅ FILTRO CRÍTICO: só última semana
        "limit": limite, 
        "restrict_sr": "on"
    }
    headers = {"User-Agent": "RadarLeads/1.0 (local)"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.raise_for_status()
        dados = res.json().get("data", {}).get("children", [])
        resultados = []
        
        agora = datetime.now(timezone.utc)
        max_idade_dias = 7  # Só aceita posts de até 7 dias
        
        for p in dados:
            d = p.get("data", {})
            texto = f"{d.get('title', '')} {d.get('selftext', '')}".strip()
            
            if not texto:
                continue
            
            criado_em = d.get("created_utc", 0)
            data_post = datetime.fromtimestamp(criado_em, tz=timezone.utc)
            diferenca = agora - data_post
            horas_atras = diferenca.total_seconds() / 3600
            dias_atras = diferenca.days
            
            # ✅ FILTRO: Ignora posts com mais de 7 dias
            if dias_atras > max_idade_dias:
                continue
            
            score = calcular_score(texto, horas_atras)
            
            # Só salva se tiver score mínimo de 30
            if score < 30:
                continue
            
            resultados.append({
                "platform": "reddit",
                "author": d.get("author", "anônimo"),
                "post_url": f"https://reddit.com{d.get('permalink')}",
                "raw_text": texto,
                "intent_score": score,
                "status": "novo",
                "created_at": agora.isoformat()
            })
            
            print(f"  ✓ [{dias_atras}d] Score {score}: {texto[:60]}...")
        
        return resultados
    except Exception as e:
        print(f"⚠️ Erro Reddit: {e}")
        return []

def salvar_no_supabase(leads):
    if not leads:
        return 0
    try:
        res = supabase.table("leads").upsert(leads, on_conflict="post_url").execute()
        return len(res.data) if res.data else 0
    except Exception as e:
        print(f"⚠️ Erro ao salvar: {e}")
        return 0

def main():
    print("=" * 60)
    print("🔍 RADAR DE LEADS - Buscando oportunidades RECENTES")
    print("📅 Filtro: Posts dos últimos 7 dias")
    print("=" * 60)
    
    buscas = [
        ("brasil", "preciso de"),
        ("brasil", "recomenda"),
        ("empreendedores", "preciso de"),
        ("empreendedores", "indicação"),
        ("freelanceBR", "procurando"),
        ("marketingdigital", "preciso de"),
    ]
    
    todos_leads = []
    for sub, termo in buscas:
        print(f"\n📌 Buscando em r/{sub}: '{termo}'")
        leads = buscar_reddit(sub, termo)
        todos_leads += leads
        print(f"  → {len(leads)} leads encontrados")
    
    if not todos_leads:
        print("\n✅ Nenhum lead recente encontrado desta vez.")
        print("💡 Dica: Tente rodar novamente mais tarde ou ajuste os subreddits.")
        return

    print(f"\n💾 Salvando {len(todos_leads)} leads no Supabase...")
    salvos = salvar_no_supabase(todos_leads)
    
    print("\n" + "=" * 60)
    print(f"✅ CONCLUÍDO: {salvos} leads salvos no Supabase.")
    print("👉 Acesse seu painel para ver e agir.")
    print("=" * 60)

if __name__ == "__main__":
    main()
