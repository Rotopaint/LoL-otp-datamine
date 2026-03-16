import requests
import time
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION (À MODIFIER)
# ==========================================
API_KEY = "RGAPI-b0d42765-7ba0-4bba-8395-eee9d8f63159"
GAME_NAME = "VeganWeakside" # Ton pseudo
TAG_LINE = "Peace"          # Ton tag (ex: EUW, 1234, etc.)

# Routage de l'API
ROUTING = "europe.api.riotgames.com"
HEADERS = {"X-Riot-Token": API_KEY}

# ==========================================
# 🛠️ FONCTIONS UTILITAIRES
# ==========================================
def get_puuid(game_name, tag_line):
    url = f"https://{ROUTING}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()['puuid']

def get_ranked_match_ids(puuid, total_games=300):
    match_ids = []
    for start in range(0, total_games, 100):
        url = f"https://{ROUTING}/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count=100"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            match_ids.extend(res.json())
        time.sleep(2.5) # Délai prudentiel
    return match_ids

# ==========================================
# 🚀 EXÉCUTION DU SCRIPT
# ==========================================
print(f"🔍 Récupération du PUUID pour {GAME_NAME}#{TAG_LINE}...")
try:
    puuid = get_puuid(GAME_NAME, TAG_LINE)
except Exception as e:
    print("❌ Erreur de PUUID (Vérifie ta clé API, ton pseudo et ton tag).", e)
    exit()

print(f"📥 Récupération de la liste des {300} dernières games Ranked...")
match_ids = get_ranked_match_ids(puuid, total_games=300)
total_matches = len(match_ids)
print(f"✅ {total_matches} match IDs trouvés. Début de l'analyse individuelle...\n")

chogath_games = []

# --- Compteurs pour le récapitulatif ---
count_success = 0
count_ignored = 0
count_api_error = 0
count_parse_error = 0

for index, match_id in enumerate(match_ids):
    url = f"https://{ROUTING}/lol/match/v5/matches/{match_id}"
    res = requests.get(url, headers=HEADERS)
    
    # 1. Gestion du Rate Limit (Erreur 429)
    if res.status_code == 429:
        retry_after = int(res.headers.get("Retry-After", 10))
        print(f"⚠️ [{index + 1}/{total_matches}] Rate limit atteint. Pause forcée de {retry_after}s...")
        time.sleep(retry_after + 1)
        res = requests.get(url, headers=HEADERS)
        
    # 2. Gestion des games inaccessibles
    if res.status_code != 200:
        print(f"❌ [{index + 1}/{total_matches}] Game {match_id} : Erreur API (Code: {res.status_code}).")
        count_api_error += 1
        time.sleep(2.5)
        continue
        
    # 3. Parsing de la game avec gestion des erreurs (Try/Except)
    try:
        match_data = res.json()
        info = match_data['info']
        participants = info['participants']
        
        # Trouver ton participant
        me = next((p for p in participants if p['puuid'] == puuid), None)
        
        if me and me['championName'] == 'Chogath':
            # Trouver l'adversaire
            my_role = me['teamPosition']
            my_team = me['teamId']
            opponent = next((p for p in participants if p['teamPosition'] == my_role and p['teamId'] != my_team), None)
            matchup = opponent['championName'] if opponent else "Unknown"
            
            game_length_sec = info.get('gameDuration', 0)
            
            # Extraire les runes en toute sécurité
            primary_style = me['perks']['styles'][0]
            secondary_style = me['perks']['styles'][1] if len(me['perks']['styles']) > 1 else {'selections': []}
            
            p_sel = primary_style.get('selections', [])
            s_sel = secondary_style.get('selections', [])
            
            keystone = p_sel[0]['perk'] if len(p_sel) > 0 else 0
            rune1 = p_sel[1]['perk'] if len(p_sel) > 1 else 0
            rune2 = p_sel[2]['perk'] if len(p_sel) > 2 else 0
            rune3 = p_sel[3]['perk'] if len(p_sel) > 3 else 0
            
            rune4 = s_sel[0]['perk'] if len(s_sel) > 0 else 0
            rune5 = s_sel[1]['perk'] if len(s_sel) > 1 else 0
            
            # Compiler
            game_info = {
                "MatchID": match_id,
                "Date": pd.to_datetime(info['gameCreation'], unit='ms').strftime('%Y-%m-%d'),
                "GameLength_Sec": game_length_sec,
                "Win": "Yes" if me['win'] else "No",
                "Matchup": matchup,
                "Role": my_role,
                "Kills": me['kills'],
                "Deaths": me['deaths'],
                "Assists": me['assists'],
                "Sum1": me['summoner1Id'],
                "Sum2": me['summoner2Id'],
                "Keystone": keystone,
                "Rune1": rune1,
                "Rune2": rune2,
                "Rune3": rune3,
                "Rune4": rune4,
                "Rune5": rune5,
                "Item0": me['item0'],
                "Item1": me['item1'],
                "Item2": me['item2'],
                "Item3": me['item3'],
                "Item4": me['item4'],
                "Item5": me['item5'],
                "Dmg": me['totalDamageDealtToChampions']
            }
            chogath_games.append(game_info)
            count_success += 1
            win_str = "Victoire" if me['win'] else "Défaite"
            print(f"🟩 [{index + 1}/{total_matches}] Game {match_id} : Ajoutée (Matchup: {matchup} | {win_str})")
            
        else:
            count_ignored += 1
            played_champ = me['championName'] if me else "Aucun"
            print(f"⏭️ [{index + 1}/{total_matches}] Game {match_id} : Ignorée (Joué : {played_champ})")
            
    except Exception as e:
        count_parse_error += 1
        print(f"⚠️ [{index + 1}/{total_matches}] Game {match_id} : Erreur de lecture des données ({e})")

    # Délai long et sécurisé entre chaque requête
    time.sleep(2.5)

# ==========================================
# 💾 SAUVEGARDE ET RÉCAPITULATIF
# ==========================================
if chogath_games:
    df = pd.DataFrame(chogath_games)
    df.to_csv("ChoGath_Matchups_Ranked.csv", index=False)

print("\n==========================================")
print("📊 RÉCAPITULATIF DE L'EXTRACTION")
print("==========================================")
print(f"Total de requêtes effectuées : {total_matches}")
print(f"🟩 Games Cho'Gath parsées avec succès : {count_success}")
print(f"⏭️ Games ignorées (Autre champion) : {count_ignored}")
print(f"❌ Erreurs serveur (API Riot) : {count_api_error}")
print(f"⚠️ Erreurs de parsing (Remake/Bug) : {count_parse_error}")
print("==========================================")

if count_success > 0:
    print(f"🎉 Le fichier 'ChoGath_Matchups_Ranked.csv' a été généré avec succès !")
else:
    print("🤔 Aucune game de Cho'Gath n'a été trouvée/sauvegardée.")