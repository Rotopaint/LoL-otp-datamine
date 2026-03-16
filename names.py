import requests
import pandas as pd

print("🌍 Connexion à l'API officielle de Riot (Data Dragon)...")

# 1. Obtenir la version du patch actuel
version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
latest_version = requests.get(version_url).json()[0]
print(f"📦 Patch actuel détecté : {latest_version}")

# 2. Télécharger les bases de données complètes
print("📥 Téléchargement des Items, Runes et Sorts...")
items_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/item.json").json()['data']
runes_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/runesReforged.json").json()
sums_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/summoner.json").json()['data']

# 3. Construire le dictionnaire dynamiquement
mapping = {0: "Empty"} # Pour les slots vides

# -- Peupler les Items --
for item_id, info in items_data.items():
    mapping[int(item_id)] = info['name']

# (Sécurité pour les items spéciaux S14/S16 qui pourraient ne pas être listés normalement)
if 2524 not in mapping: mapping[2524] = "Bandlepipes"
if 2525 not in mapping: mapping[2525] = "Bandlepipes"
if 2502 not in mapping: mapping[2502] = "Unending Despair"
if 2504 not in mapping: mapping[2504] = "Kaenic Rookern"
if 6655 not in mapping: mapping[6655] = "Luden's Companion"
if 3118 not in mapping: mapping[3118] = "Malignance"

# -- Peupler les Runes (Keystones + Petites runes) --
for tree in runes_data:
    mapping[tree['id']] = tree['name'] # Nom de l'arbre principal
    for slot in tree['slots']:
        for rune in slot['runes']:
            mapping[rune['id']] = rune['name'] # Ex: Nimbus Cloak, Bone Plating...

# -- Peupler les Sorts d'invocateur --
for _, info in sums_data.items():
    mapping[int(info['key'])] = info['name']

print("✅ Dictionnaire construit avec succès ! Traduction en cours...")

# 4. Charger ton CSV et appliquer le dictionnaire
try:
    df = pd.read_csv('ChoGath_Matchups_Ranked.csv')
    
    # Liste des colonnes qui contiennent des IDs à traduire
    cols_to_map = ['Sum1', 'Sum2', 'Keystone', 'Rune1', 'Rune2', 'Rune3', 'Rune4', 'Rune5', 
                   'Item0', 'Item1', 'Item2', 'Item3', 'Item4', 'Item5']
    
    # Remplacement (si un ID est inconnu, il garde son numéro pour éviter de créer des trous)
    for col in cols_to_map:
        if col in df.columns:
            df[col] = df[col].map(mapping).fillna(df[col])
            
    # 5. Sauvegarder le résultat final
    df.to_csv('ChoGath_Matchups_Translated.csv', index=False)
    print("🎉 BOOM ! Fichier traduit ! Ouvre 'ChoGath_Matchups_Translated.csv' pour voir la magie opérer.")

except FileNotFoundError:
    print("❌ Erreur : Le fichier 'ChoGath_Matchups_Ranked.csv' est introuvable dans ce dossier.")