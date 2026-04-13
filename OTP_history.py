import requests
import time
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION (TO BE MODIFIED BY USER)
# ==========================================
API_KEY = "RGAPI-YOUR-API-KEY-HERE"
GAME_NAME = "YourName"     # e.g., "VeganWeakside"
TAG_LINE = "Tag"           # e.g., "EUW" or "1234"
TARGET_CHAMPION = "Chogath" # Champion you want to track
TOTAL_GAMES_TO_CHECK = 5   # Number of recent ranked games to scan

# API Routing (Change if you are not in Europe)
# Options: europe.api.riotgames.com, americas.api.riotgames.com, asia.api.riotgames.com
ROUTING = "europe.api.riotgames.com" 
HEADERS = {"X-Riot-Token": API_KEY}

# ==========================================
# 🛠️ RIOT API FUNCTIONS
# ==========================================
def get_puuid(game_name, tag_line):
    url = f"https://{ROUTING}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()['puuid']

def get_ranked_match_ids(puuid, total_games=200):
    match_ids = []
    # Riot API allows fetching up to 100 match IDs per request
    for start in range(0, total_games, 100):
        # Dynamically calculate the count to avoid over-fetching
        count = min(100, total_games - start)
        
        url = f"https://{ROUTING}/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count={count}"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            match_ids.extend(res.json())
        time.sleep(2.5) # Safety delay for rate limits
        
    return match_ids

# ==========================================
# 🛠️ DATA DRAGON TRANSLATION FUNCTIONS
# ==========================================
def build_translation_mapping():
    print("🌍 Connecting to Riot Data Dragon (Fetching latest patch info)...")
    version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
    latest_version = requests.get(version_url).json()[0]
    print(f"📦 Latest patch detected: {latest_version}")

    print("📥 Downloading Items, Runes, and Summoner Spells databases...")
    items_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/item.json").json()['data']
    runes_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/runesReforged.json").json()
    sums_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/summoner.json").json()['data']

    mapping = {0: "Empty"}

    # -- Map Items --
    for item_id, info in items_data.items():
        mapping[int(item_id)] = info['name']

    # Manual overrides for special items (e.g., Ornn upgrades or newly added items)
    custom_items = {
        2524: "Bandlepipes", 2525: "Bandlepipes",
        2502: "Unending Despair", 2504: "Kaenic Rookern",
        6655: "Luden's Companion", 3118: "Malignance"
    }
    for c_id, c_name in custom_items.items():
        if c_id not in mapping: mapping[c_id] = c_name

    # -- Map Runes --
    for tree in runes_data:
        mapping[tree['id']] = tree['name'] # Main tree (e.g., Resolve)
        for slot in tree['slots']:
            for rune in slot['runes']:
                mapping[rune['id']] = rune['name'] # Runes (e.g., Grasp of the Undying)

    # -- Map Summoner Spells --
    for _, info in sums_data.items():
        mapping[int(info['key'])] = info['name']

    return mapping

# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================
def main():
    print(f"🔍 Fetching PUUID for {GAME_NAME}#{TAG_LINE}...")
    try:
        puuid = get_puuid(GAME_NAME, TAG_LINE)
    except Exception as e:
        print("❌ Error fetching PUUID (Check API Key, Game Name, and Tag Line).", e)
        return

    print(f"📥 Fetching the last {TOTAL_GAMES_TO_CHECK} Ranked games...")
    match_ids = get_ranked_match_ids(puuid, total_games=TOTAL_GAMES_TO_CHECK)
    total_matches = len(match_ids)
    print(f"✅ {total_matches} match IDs found. Starting individual match analysis...\n")

    tracked_games = []
    count_success, count_ignored, count_api_error, count_parse_error = 0, 0, 0, 0

    for index, match_id in enumerate(match_ids):
        url = f"https://{ROUTING}/lol/match/v5/matches/{match_id}"
        res = requests.get(url, headers=HEADERS)

        # 1. Rate Limit Handling (Error 429)
        if res.status_code == 429:
            retry_after = int(res.headers.get("Retry-After", 10))
            print(f"⚠️ [{index + 1}/{total_matches}] Rate limit hit. Sleeping for {retry_after}s...")
            time.sleep(retry_after + 1)
            res = requests.get(url, headers=HEADERS)

        # 2. Server Error Handling
        if res.status_code != 200:
            print(f"❌ [{index + 1}/{total_matches}] Game {match_id}: API Error (Code: {res.status_code}).")
            count_api_error += 1
            time.sleep(2.5)
            continue

        # 3. Match Parsing
        try:
            match_data = res.json()
            info = match_data['info']
            participants = info['participants']

            # Find our player in the game
            me = next((p for p in participants if p['puuid'] == puuid), None)

            if me and me['championName'] == TARGET_CHAMPION:
                my_role = me['teamPosition']
                my_team = me['teamId']
                
                # Find the direct lane opponent
                opponent = next((p for p in participants if p['teamPosition'] == my_role and p['teamId'] != my_team), None)
                matchup = opponent['championName'] if opponent else "Unknown"
                
                game_length_sec = info.get('gameDuration', 0)
                
                # Extract Runes securely
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
                tracked_games.append(game_info)
                count_success += 1
                win_str = "Win" if me['win'] else "Loss"
                print(f"🟩 [{index + 1}/{total_matches}] Game added (Matchup: {matchup} | {win_str})")
            else:
                count_ignored += 1
                played_champ = me['championName'] if me else "None"
                print(f"⏭️ [{index + 1}/{total_matches}] Game ignored (Played: {played_champ})")

        except Exception as e:
            count_parse_error += 1
            print(f"⚠️ [{index + 1}/{total_matches}] Match parsing error ({e})")

        time.sleep(2.5) # Required delay to respect Riot's rate limit

    # ==========================================
    # 💾 TRANSLATION & CSV SAVING
    # ==========================================
    if tracked_games:
        print("\n==========================================")
        print("✨ EXTRACTION COMPLETE. STARTING TRANSLATION...")
        print("==========================================")
        
        df = pd.DataFrame(tracked_games)
        mapping = build_translation_mapping()
        
        cols_to_map = ['Sum1', 'Sum2', 'Keystone', 'Rune1', 'Rune2', 'Rune3', 'Rune4', 'Rune5', 
                       'Item0', 'Item1', 'Item2', 'Item3', 'Item4', 'Item5']
                       
        for col in cols_to_map:
            if col in df.columns:
                df[col] = df[col].map(mapping).fillna(df[col])
        
        output_filename = f"{TARGET_CHAMPION}_Matchups_Translated.csv"
        df.to_csv(output_filename, index=False)
        
        print("\n==========================================")
        print("📊 SUMMARY")
        print("==========================================")
        print(f"Total requests made: {total_matches}")
        print(f"🟩 {TARGET_CHAMPION} games parsed successfully: {count_success}")
        print(f"⏭️ Games ignored (Other champions): {count_ignored}")
        print(f"❌ Server Errors: {count_api_error}")
        print(f"⚠️ Parsing Errors: {count_parse_error}")
        print("==========================================")
        print(f"🎉 SUCCESS! File '{output_filename}' has been generated!")
    else:
        print("\n🤔 No games found for the specified champion.")

if __name__ == "__main__":
    main()