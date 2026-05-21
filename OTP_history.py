import requests
import time
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_KEY = "RGAPI-d8ef9c7c-bfe5-4779-b42d-b252eb8fe1c1"
GAME_NAME = "FractalBlur"
TAG_LINE = "123"
TARGET_CHAMPION = "Chogath"
TOTAL_GAMES_TO_CHECK = 200

ROUTING = "europe.api.riotgames.com"
HEADERS = {"X-Riot-Token": API_KEY}

# ==========================================
# ⚙️ ITEM FILTER CONSTANTS
# ==========================================
PRICE_THRESHOLD = 2000

CONSUMABLES = {2003, 2031, 2033, 3340, 3363, 3364, 2138, 2139, 2140}

WHITELIST_IDS = {
    1001,                               # Boots of Speed
    3006, 3009, 3020, 3047, 3111,       # Boots tier 2
    3117, 3158,                         # Boots tier 2 (suite)
    2422,                               # Slightly Magical Boots
    1082,                               # Dark Seal
    3041,                               # Mejai's Soulstealer
    3076,                               # Bramble Vest
    3916,                               # Oblivion Orb
    2055,                               # Control Ward
}

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
    for start in range(0, total_games, 100):
        count = min(100, total_games - start)
        url = f"https://{ROUTING}/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count={count}"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            match_ids.extend(res.json())
        time.sleep(2.5)
    return match_ids

def fetch_timeline(match_id):
    url = f"https://{ROUTING}/lol/match/v5/matches/{match_id}/timeline"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 429:
        retry_after = int(res.headers.get("Retry-After", 10))
        time.sleep(retry_after + 1)
        res = requests.get(url, headers=HEADERS)
    return res.json() if res.status_code == 200 else None

# ==========================================
# 🛠️ DATA DRAGON
# ==========================================
def build_translation_mapping():
    print("🌍 Connecting to Riot Data Dragon...")
    latest_version = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]
    print(f"📦 Latest patch: {latest_version}")

    print("📥 Downloading Items, Runes, and Summoner Spells...")
    items_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/item.json").json()['data']
    runes_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/runesReforged.json").json()
    sums_data  = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/summoner.json").json()['data']

    mapping = {0: "Empty"}

    # Items
    for item_id, info in items_data.items():
        mapping[int(item_id)] = info['name']

    # Manual overrides
    custom_items = {
        2524: "Bandlepipes", 2525: "Bandlepipes",
        2502: "Unending Despair", 2504: "Kaenic Rookern",
        6655: "Luden's Companion", 3118: "Malignance"
    }
    for c_id, c_name in custom_items.items():
        if c_id not in mapping:
            mapping[c_id] = c_name

    # Runes
    for tree in runes_data:
        mapping[tree['id']] = tree['name']
        for slot in tree['slots']:
            for rune in slot['runes']:
                mapping[rune['id']] = rune['name']

    # Summoner spells
    for _, info in sums_data.items():
        mapping[int(info['key'])] = info['name']

    # Build component filter : items sous le seuil de prix
    component_ids = set()
    for item_id, info in items_data.items():
        price = info.get('gold', {}).get('total', 0)
        if price < PRICE_THRESHOLD:
            component_ids.add(int(item_id))

    # Jungle starters résolus dynamiquement par nom
    jungle_keywords = ["Mosstomper", "Scorchclaw", "Gustwalker"]
    jungle_starter_ids = set()
    for item_id, info in items_data.items():
        if any(kw in info['name'] for kw in jungle_keywords):
            jungle_starter_ids.add(int(item_id))
            print(f"  🌿 Jungle starter: {info['name']} (ID: {item_id})")

    component_ids -= WHITELIST_IDS
    component_ids -= jungle_starter_ids

    return mapping, component_ids, jungle_starter_ids

# ==========================================
# 🛠️ TIMELINE PARSING
# ==========================================
def parse_item_sequence(timeline, participant_id, mapping, component_ids):
    """Séquence d'items finaux dans l'ordre d'achat, corrigée des UNDO et SOLD."""
    sequence = []

    for frame in timeline['info']['frames']:
        for event in frame['events']:
            if event.get('participantId') != participant_id:
                continue

            if event['type'] == 'ITEM_PURCHASED':
                item_id = event['itemId']
                if item_id in CONSUMABLES or item_id in component_ids:
                    continue
                name = mapping.get(item_id, str(item_id))
                ts   = event['timestamp'] // 1000
                sequence.append([name, ts])

            elif event['type'] == 'ITEM_SOLD':
                item_id = event['itemId']
                if item_id in CONSUMABLES or item_id in component_ids:
                    continue
                sold_name = mapping.get(item_id, str(item_id))
                for i in range(len(sequence) - 1, -1, -1):
                    if sequence[i][0] == sold_name:
                        sequence.pop(i)
                        break

            elif event['type'] == 'ITEM_UNDO':
                before_id = event.get('beforeId', 0)
                after_id  = event.get('afterId', 0)
                if before_id and before_id not in CONSUMABLES and before_id not in component_ids:
                    before_name = mapping.get(before_id, str(before_id))
                    for i in range(len(sequence) - 1, -1, -1):
                        if sequence[i][0] == before_name:
                            sequence.pop(i)
                            break
                if after_id and after_id not in CONSUMABLES and after_id not in component_ids:
                    after_name = mapping.get(after_id, str(after_id))
                    sequence.append([after_name, event['timestamp'] // 1000])

    return sequence

def get_gold_diffs(timeline, my_pid, opp_pid, my_team_ids, opp_team_ids):
    """GoldDiff (lane + team) toutes les 5 minutes sur toute la durée de la game."""
    frames = timeline['info']['frames']
    result = {}

    for minute in range(5, len(frames), 5):
        pf = frames[minute]['participantFrames']

        # Lane diff
        my_gold  = pf[str(my_pid)].get('totalGold', 0)
        opp_gold = pf[str(opp_pid)].get('totalGold', 0) if opp_pid else 0
        result[f'GoldDiff_{minute}'] = my_gold - opp_gold

        # Team diff
        my_team_gold  = sum(pf[str(pid)].get('totalGold', 0) for pid in my_team_ids)
        opp_team_gold = sum(pf[str(pid)].get('totalGold', 0) for pid in opp_team_ids)
        result[f'TeamGoldDiff_{minute}'] = my_team_gold - opp_team_gold

    return result

def fmt_seq(sequence):
    """Formate la séquence : 'DShield@0:32 > Heartsteel@12:41'"""
    parts = []
    for name, ts in sequence:
        parts.append(f"{name}@{ts//60}:{ts%60:02d}")
    return " > ".join(parts)

# ==========================================
# 🚀 MAIN
# ==========================================
def main():
    print(f"🔍 Fetching PUUID for {GAME_NAME}#{TAG_LINE}...")
    try:
        puuid = get_puuid(GAME_NAME, TAG_LINE)
    except Exception as e:
        print("❌ Error fetching PUUID.", e)
        return

    # Build translation tables AVANT la boucle
    mapping, component_ids, jungle_starter_ids = build_translation_mapping()
    print(f"  ✅ {len(jungle_starter_ids)} jungle starter(s) whitelisted.")

    print(f"\n📥 Fetching the last {TOTAL_GAMES_TO_CHECK} Ranked games...")
    match_ids     = get_ranked_match_ids(puuid, total_games=TOTAL_GAMES_TO_CHECK)
    total_matches = len(match_ids)
    print(f"✅ {total_matches} match IDs found. Starting analysis...\n")

    tracked_games = []
    count_success, count_ignored, count_api_error, count_parse_error = 0, 0, 0, 0

    for index, match_id in enumerate(match_ids):
        url = f"https://{ROUTING}/lol/match/v5/matches/{match_id}"
        res = requests.get(url, headers=HEADERS)

        if res.status_code == 429:
            retry_after = int(res.headers.get("Retry-After", 10))
            print(f"⚠️ [{index+1}/{total_matches}] Rate limit. Sleeping {retry_after}s...")
            time.sleep(retry_after + 1)
            res = requests.get(url, headers=HEADERS)

        if res.status_code != 200:
            print(f"❌ [{index+1}/{total_matches}] API Error ({res.status_code}).")
            count_api_error += 1
            time.sleep(2.5)
            continue

        try:
            match_data   = res.json()
            info         = match_data['info']
            participants = info['participants']

            me = next((p for p in participants if p['puuid'] == puuid), None)

            if me and me['championName'] == TARGET_CHAMPION:
                my_role = me['teamPosition']
                my_team = me['teamId']
                my_pid  = me['participantId']

                opponent = next(
                    (p for p in participants if p['teamPosition'] == my_role and p['teamId'] != my_team),
                    None
                )
                matchup = opponent['championName'] if opponent else "Unknown"
                opp_pid = opponent['participantId'] if opponent else None

                my_team_ids  = [p['participantId'] for p in participants if p['teamId'] == my_team]
                opp_team_ids = [p['participantId'] for p in participants if p['teamId'] != my_team]

                # Timeline
                timeline = fetch_timeline(match_id)
                time.sleep(2.5)

                if timeline:
                    sequence   = parse_item_sequence(timeline, my_pid, mapping, component_ids)
                    gold_diffs = get_gold_diffs(timeline, my_pid, opp_pid, my_team_ids, opp_team_ids)
                else:
                    sequence   = []
                    gold_diffs = {}

                # Runes
                primary_style   = me['perks']['styles'][0]
                secondary_style = me['perks']['styles'][1] if len(me['perks']['styles']) > 1 else {'selections': []}
                p_sel = primary_style.get('selections', [])
                s_sel = secondary_style.get('selections', [])

                keystone = p_sel[0]['perk'] if len(p_sel) > 0 else 0
                rune1    = p_sel[1]['perk'] if len(p_sel) > 1 else 0
                rune2    = p_sel[2]['perk'] if len(p_sel) > 2 else 0
                rune3    = p_sel[3]['perk'] if len(p_sel) > 3 else 0
                rune4    = s_sel[0]['perk'] if len(s_sel) > 0 else 0
                rune5    = s_sel[1]['perk'] if len(s_sel) > 1 else 0

                game_info = {
                    "MatchID":        match_id,
                    "Date":           pd.to_datetime(info['gameCreation'], unit='ms').strftime('%Y-%m-%d'),
                    "GameLength_Sec": info.get('gameDuration', 0),
                    "Win":            "Yes" if me['win'] else "No",
                    "Matchup":        matchup,
                    "Role":           my_role,
                    "Kills":          me['kills'],
                    "Deaths":         me['deaths'],
                    "Assists":        me['assists'],
                    "Sum1":           mapping.get(me['summoner1Id'], me['summoner1Id']),
                    "Sum2":           mapping.get(me['summoner2Id'], me['summoner2Id']),
                    "Keystone":       mapping.get(keystone, keystone),
                    "Rune1":          mapping.get(rune1, rune1),
                    "Rune2":          mapping.get(rune2, rune2),
                    "Rune3":          mapping.get(rune3, rune3),
                    "Rune4":          mapping.get(rune4, rune4),
                    "Rune5":          mapping.get(rune5, rune5),
                    "Item0":          mapping.get(me['item0'], me['item0']),
                    "Item1":          mapping.get(me['item1'], me['item1']),
                    "Item2":          mapping.get(me['item2'], me['item2']),
                    "Item3":          mapping.get(me['item3'], me['item3']),
                    "Item4":          mapping.get(me['item4'], me['item4']),
                    "Item5":          mapping.get(me['item5'], me['item5']),
                    "ItemSequence":   fmt_seq(sequence),
                    "Dmg":            me['totalDamageDealtToChampions'],
                    **gold_diffs,     # GoldDiff_5, GoldDiff_10, ... + TeamGoldDiff_5, ...
                }
                tracked_games.append(game_info)
                count_success += 1
                win_str = "Win" if me['win'] else "Loss"
                print(f"🟩 [{index+1}/{total_matches}] {matchup} | {win_str} | {fmt_seq(sequence)}")

            else:
                count_ignored += 1
                played_champ = me['championName'] if me else "None"
                print(f"⏭️ [{index+1}/{total_matches}] Ignored ({played_champ})")

        except Exception as e:
            count_parse_error += 1
            print(f"⚠️ [{index+1}/{total_matches}] Parse error: {e}")

        time.sleep(2.5)

    # ==========================================
    # 💾 CSV EXPORT
    # ==========================================
    if tracked_games:
        df = pd.DataFrame(tracked_games)
        output_filename = f"{TARGET_CHAMPION}_Matchups_Translated.csv"
        df.to_csv(output_filename, index=False)

        print("\n==========================================")
        print("📊 SUMMARY")
        print("==========================================")
        print(f"Total requests:            {total_matches}")
        print(f"🟩 {TARGET_CHAMPION} games parsed: {count_success}")
        print(f"⏭️ Ignored (other champs):  {count_ignored}")
        print(f"❌ Server errors:           {count_api_error}")
        print(f"⚠️ Parse errors:            {count_parse_error}")
        print("==========================================")
        print(f"🎉 File '{output_filename}' generated!")
    else:
        print("\n🤔 No games found for the specified champion.")

if __name__ == "__main__":
    main()
