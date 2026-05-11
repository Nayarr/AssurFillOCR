from difflib import get_close_matches

MARQUES: frozenset[str] = frozenset({
    'ABARTH', 'AIWAYS', 'ALEKO', 'ALFA ROMEO', 'ALPINE RENAULT', 'ARO', 'ASIA',
    'ASTON MARTIN', 'AUDI', 'AUSTIN', 'AUSTIN HEALEY', 'AUTOBIANCHI', 'AUVERLAND',
    'BEDFORD', 'BEE BEE AUTOMOTIVE', 'BENTLEY', 'BENTLEY UK', 'BERTONE', 'BMW',
    'BUICK', 'BYD', 'CADILLAC', 'CHEVROLET', 'CHEVROLET US', 'CHRYSLER', 'CITROEN',
    'COURB', 'CUPRA', 'DACIA', 'DAEWOO', 'DAF', 'DAIHATSU', 'DAIMLER', 'DATSUN',
    'DODGE', 'DODGE US', 'DS', 'EBRO', 'FERRARI', 'FEST', 'FIAT', 'FISKER',
    'FORD', 'FORD US', 'FSO-POLSKI', 'GAC GONOW', 'GME', 'GRANDIN', 'HONDA',
    'HONGQI', 'HUMMER', 'HYUNDAI', 'INEOS', 'INFINITI', 'INNOCENTI', 'ISUZU',
    'IVECO', 'JAECOO', 'JAGUAR', 'JEEP', 'JENSEN', 'KIA', 'LADA', 'LAMBORGHINI',
    'LANCIA', 'LAND ROVER', 'LDV', 'LEAPMOTOR', 'LEXUS', 'LINCOLN', 'LOTUS',
    'LYNK&CO', 'MAC LAREN', 'MAHINDRA', 'MAN', 'MARUTI', 'MASERATI', 'MATRA',
    'MAXUS', 'MAZDA', 'MCC', 'MEGA', 'MERCEDES', 'MG', 'MG UK', 'MIA', 'MINI',
    'MITSUBISHI', 'MORGAN', 'MPM MOTORS', 'NISSAN', 'OLDSMOBILE', 'OMODA', 'OPEL',
    'PANHARD', 'PEUGEOT', 'PGO', 'PIAGGIO', 'PLYMOUTH', 'POLESTAR', 'PONTIAC',
    'PONTIAC US', 'PORSCHE', 'PROTON', 'RENAULT', 'ROLLS ROYCE', 'ROVER', 'SAAB',
    'SANTANA', 'SEAT', 'SECMA', 'SERES DFSK', 'SKODA', 'SMART', 'SSANGYONG',
    'SUBARU', 'SUNBEAM', 'SUZUKI', 'TALBOT', 'TATA', 'TESLA', 'THINK', 'TOYOTA',
    'TOYOTA US', 'TRIUMPH', 'TVR', 'UMM', 'VINFAST', 'VOLKSWAGEN', 'VOLVO',
    'XPENG', 'ZASTAVA', 'ZAZ',
})

_MODELES_BRUTS: dict[str, list[str]] = {
    'ABARTH':       ['124 Spider', '500 I', '500 II', '500 III', '500C', '595', '695', 'Punto', 'Stilo'],
    'AIWAYS':       ['U5', 'U6'],
    'ALFA ROMEO':   ['147', '156', '159', '166', 'Giulia', 'Giulietta', 'MiTo', 'Stelvio', 'Tonale'],
    'ASTON MARTIN': ['DB7', 'DB9', 'DB11', 'DBS', 'Vantage', 'Rapide'],
    'AUDI':         ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'Q2', 'Q3', 'Q4 e-tron', 'Q5', 'Q7', 'Q8', 'R8', 'RS3', 'RS4', 'RS5', 'RS6', 'RS7', 'TT'],
    'BENTLEY':      ['Bentayga', 'Continental', 'Flying Spur', 'Mulsanne'],
    'BMW':          ['i3', 'i4', 'i7', 'iX', 'Série 1', 'Série 2', 'Série 3', 'Série 4', 'Série 5', 'Série 6', 'Série 7', 'Série 8', 'X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'X7', 'Z3', 'Z4'],
    'BYD':          ['Atto 3', 'Han', 'Seal', 'Tang'],
    'CHEVROLET':    ['Camaro', 'Captiva', 'Corvette', 'Cruze', 'Epica', 'Equinox', 'Lacetti', 'Malibu', 'Matiz', 'Nubira', 'Orlando', 'Spark', 'Suburban', 'Tahoe', 'Traverse', 'Trax', 'Volt'],
    'CHRYSLER':     ['300C', 'Grand Voyager', 'Neon', 'PT Cruiser', 'Sebring', 'Stratus', 'Voyager'],
    'CITROEN':      ['Berlingo', 'C1', 'C2', 'C3', 'C3 Aircross', 'C4', 'C4 Cactus', 'C4 Picasso', 'C5', 'C5 Aircross', 'C5 X', 'C6', 'C8', 'Dispatch', 'DS3', 'DS4', 'DS5', 'Grand C4', 'Jumpy', 'Nemo', 'Saxo', 'SpaceTourer', 'Xantia', 'Xsara', 'ZX'],
    'CUPRA':        ['Ateca', 'Born', 'Formentor', 'Leon'],
    'DACIA':        ['Bigster', 'Duster', 'Jogger', 'Logan', 'Lodgy', 'Sandero', 'Sandero Stepway', 'Spring'],
    'DAEWOO':       ['Espero', 'Kalos', 'Lacetti', 'Lanos', 'Matiz', 'Nubira', 'Tacuma'],
    'DODGE':        ['Caliber', 'Challenger', 'Charger', 'Dart', 'Durango', 'Journey', 'Neon', 'Ram', 'Viper'],
    'DS':           ['DS 3', 'DS 3 Crossback', 'DS 4', 'DS 5', 'DS 7', 'DS 9'],
    'FERRARI':      ['296 GTB', '488', '575', '612', 'California', 'F430', 'F8', 'GTC4Lusso', 'LaFerrari', 'Portofino', 'Roma', 'SF90', 'Testarossa'],
    'FIAT':         ['124', '500', '500L', '500X', 'Barchetta', 'Bravo', 'Croma', 'Doblo', 'Ducato', 'Grande Punto', 'Idea', 'Linea', 'Multipla', 'Panda', 'Punto', 'Qubo', 'Scudo', 'Sedici', 'Siena', 'Stilo', 'Tipo', 'Ulysse'],
    'FORD':         ['B-Max', 'C-Max', 'Edge', 'EcoSport', 'Escape', 'Explorer', 'Fiesta', 'Focus', 'Fusion', 'Galaxy', 'Grand C-Max', 'Ka', 'Ka+', 'Kuga', 'Maverick', 'Mondeo', 'Mustang', 'Mustang Mach-E', 'Puma', 'Ranger', 'S-Max', 'Transit', 'Transit Connect'],
    'HONDA':        ['Accord', 'City', 'Civic', 'CR-V', 'e', 'FR-V', 'HR-V', 'Insight', 'Jazz', 'Legend', 'NSX', 'Pilot', 'Prelude', 'Ridgeline', 'Stream', 'ZR-V'],
    'HYUNDAI':      ['Bayon', 'Coupé', 'Elantra', 'Getz', 'H-1', 'i10', 'i20', 'i30', 'i40', 'i50', 'i800', 'Ioniq', 'Ioniq 5', 'Ioniq 6', 'ix20', 'ix35', 'Kona', 'Santa Fe', 'Staria', 'Terracan', 'Trajet', 'Tucson', 'Veloster', 'Venue'],
    'JAGUAR':       ['E-Pace', 'E-Type', 'F-Pace', 'F-Type', 'I-Pace', 'S-Type', 'X-Type', 'XE', 'XF', 'XJ'],
    'JEEP':         ['Cherokee', 'Commander', 'Compass', 'Gladiator', 'Grand Cherokee', 'Patriot', 'Renegade', 'Wrangler'],
    'KIA':          ['Carens', 'Ceed', 'Cerato', 'EV6', 'EV9', 'Niro', 'Optima', 'Picanto', 'ProCeed', 'Rio', 'Sorento', 'Soul', 'Sportage', 'Stinger', 'Stonic', 'Telluride', 'Venga', 'XCeed'],
    'LAMBORGHINI':  ['Aventador', 'Diablo', 'Gallardo', 'Huracán', 'Murciélago', 'Urus'],
    'LANCIA':       ['Delta', 'Lybra', 'Musa', 'Phedra', 'Thesis', 'Ypsilon'],
    'LAND ROVER':   ['Defender', 'Discovery', 'Discovery Sport', 'Freelander', 'Range Rover', 'Range Rover Evoque', 'Range Rover Sport', 'Range Rover Velar'],
    'LEXUS':        ['CT', 'ES', 'GS', 'IS', 'LC', 'LFA', 'LS', 'NX', 'RC', 'RX', 'UX'],
    'MASERATI':     ['GranTurismo', 'Ghibli', 'Grecale', 'Grancabrio', 'Levante', 'MC20', 'Quattroporte'],
    'MAZDA':        ['2', '3', '5', '6', 'BT-50', 'CX-3', 'CX-30', 'CX-5', 'CX-60', 'CX-7', 'CX-9', 'MX-5', 'MX-30', 'RX-7', 'RX-8'],
    'MERCEDES':     ['A', 'B', 'C', 'CLA', 'CLS', 'E', 'EQA', 'EQB', 'EQC', 'EQE', 'EQS', 'G', 'GLA', 'GLB', 'GLC', 'GLE', 'GLK', 'GLS', 'ML', 'S', 'SL', 'SLC', 'SLK', 'Sprinter', 'Vito', 'X'],
    'MINI':         ['Cabrio', 'Clubman', 'Cooper', 'Countryman', 'Hatch', 'One', 'Paceman'],
    'MITSUBISHI':   ['ASX', 'Colt', 'Eclipse Cross', 'Galant', 'L200', 'Lancer', 'Montero', 'Outlander', 'Outlander PHEV', 'Pajero', 'Space Star'],
    'NISSAN':       ['350Z', '370Z', 'Ariya', 'Juke', 'Leaf', 'Micra', 'Murano', 'Navara', 'Note', 'NV200', 'Pathfinder', 'Pixo', 'Primastar', 'Pulsar', 'Qashqai', 'Skyline', 'Terrano', 'Tiida', 'X-Trail', 'Zoe'],
    'OPEL':         ['Adam', 'Agila', 'Ampera', 'Antara', 'Astra', 'Combo', 'Corsa', 'Crossland', 'Frontera', 'Grandland', 'Insignia', 'Meriva', 'Mokka', 'Omega', 'Signum', 'Tigra', 'Vectra', 'Vivaro', 'Zafira'],
    'PEUGEOT':      ['1007', '106', '107', '108', '2008', '205', '206', '207', '208', '3008', '306', '307', '308', '4007', '4008', '406', '407', '408', '5008', '508', 'Bipper', 'Expert', 'iOn', 'Partner', 'Rifter', 'Traveller'],
    'PORSCHE':      ['718 Boxster', '718 Cayman', '911', '918', 'Cayenne', 'Macan', 'Panamera', 'Taycan'],
    'RENAULT':      ['Arkana', 'Austral', 'Captur', 'Clio', 'Dokker', 'Duster', 'Espace', 'Express', 'Fluence', 'Grand Modus', 'Grand Scénic', 'Kadjar', 'Kangoo', 'Koleos', 'Laguna', 'Latitude', 'Master', 'Megane', 'Modus', 'Safrane', 'Scénic', 'Scenic E-Tech', 'Symbol', 'Trafic', 'Twingo', 'Twizy', 'Vel Satis', 'Wind', 'Zoe'],
    'SEAT':         ['Altea', 'Arona', 'Ateca', 'Cordoba', 'Exeo', 'Ibiza', 'Leon', 'Mii', 'Tarraco', 'Toledo'],
    'SKODA':        ['Citigo', 'Enyaq', 'Fabia', 'Kamiq', 'Karoq', 'Kodiaq', 'Octavia', 'Rapid', 'Scala', 'Superb', 'Yeti'],
    'SMART':        ['EQ Fortwo', 'Forfour', 'Forjoy', 'Fortwo'],
    'SUBARU':       ['BRZ', 'Crosstek', 'Forester', 'Impreza', 'Legacy', 'Levorg', 'Outback', 'WRX', 'XV'],
    'SUZUKI':       ['Alto', 'Baleno', 'Celerio', 'Ignis', 'Jimny', 'Kizashi', 'Liana', 'S-Cross', 'Splash', 'Swift', 'SX4', 'Vitara'],
    'TESLA':        ['Cybertruck', 'Model 3', 'Model S', 'Model X', 'Model Y', 'Roadster'],
    'TOYOTA':       ['4Runner', 'Auris', 'Avensis', 'Aygo', 'C-HR', 'Camry', 'Corolla', 'GR86', 'GR Yaris', 'Hilux', 'Land Cruiser', 'Mirai', 'Proace', 'Prius', 'RAV4', 'Supra', 'Urban Cruiser', 'Verso', 'Yaris', 'Yaris Cross'],
    'VOLKSWAGEN':   ['Amarok', 'Arteon', 'Caddy', 'Caravelle', 'Crafter', 'Fox', 'Golf', 'ID.3', 'ID.4', 'ID.5', 'ID.7', 'Jetta', 'Lupo', 'Multivan', 'Passat', 'Phaeton', 'Polo', 'Scirocco', 'Sharan', 'T-Cross', 'T-Roc', 'Taigo', 'Tiguan', 'Touareg', 'Touran', 'Transporter', 'Up!'],
    'VOLVO':        ['C30', 'C40', 'EX30', 'EX90', 'S40', 'S60', 'S80', 'S90', 'V40', 'V50', 'V60', 'V70', 'V90', 'XC40', 'XC60', 'XC70', 'XC90'],
}

# Ensemble de tous les modeles en majuscules
TOUS_MODELES: frozenset[str] = frozenset(
    m.upper() for ms in _MODELES_BRUTS.values() for m in ms
)

# Table inverse : modele (majuscules) → marque
_MODELE_VERS_MARQUE: dict[str, str] = {}
for _marque, _modeles in _MODELES_BRUTS.items():
    for _mod in _modeles:
        _maj = _mod.upper()
        if _maj not in _MODELE_VERS_MARQUE:
            _MODELE_VERS_MARQUE[_maj] = _marque

# Puissance fiscale maximale admise sur une CG
MAX_PF = 12
PF_MAX = MAX_PF  # alias de compatibilité


def marque_approx(chaine: str, seuil: float = 0.82) -> str | None:
    """Retourne la marque connue la plus proche de la chaine, ou None."""
    maj = chaine.upper().strip()
    if maj in MARQUES:
        return maj
    correspondances = get_close_matches(maj, MARQUES, n=1, cutoff=seuil)
    return correspondances[0] if correspondances else None


# Alias pour compatibilité
ALL_MODELS = TOUS_MODELES
fuzzy_brand = marque_approx


def _ressemble_label(chaine: str) -> bool:
    """Vrai si la chaine ressemble a un label OCR capturé en guise de valeur."""
    import re
    return bool(re.search(r'[a-z]{3,}', chaine)) and len(chaine.split()) >= 2


def _extraire_modele_depuis_denomination(denomination: str) -> str | None:
    """Extrait un modèle connu depuis une dénomination commerciale complexe.
    Ex: 'TIPO LIFE SEDAN' → 'TIPO', 'NEW BERLINGO 1.6 HDI' → 'BERLINGO'
    """
    mots = [m for m in denomination.upper().split() if len(m) >= 3]
    for mot in mots:
        if mot in TOUS_MODELES:
            return mot
        resultats = get_close_matches(mot, TOUS_MODELES, n=1, cutoff=0.88)
        if resultats:
            return resultats[0]
    return None


def fix_marque_modele(donnees: dict) -> None:
    """Corrige marque/modele : normalisation, inversion, déduction, correction floue."""
    score_marque = donnees.pop("_score_marque", 1.0)
    donnees.pop("_score_modele", None)

    marque_brute = donnees.get("marque")
    modele_brut = donnees.get("modele")

    # Supprime les valeurs qui sont en fait des labels OCR
    if modele_brut and _ressemble_label(modele_brut):
        donnees["modele"] = None
        modele_brut = None
    if marque_brute and _ressemble_label(marque_brute):
        donnees["marque"] = None
        marque_brute = None

    marque_corr = marque_approx(marque_brute) if marque_brute else None
    modele_corr = marque_approx(modele_brut) if modele_brut else None

    marque_reconnue = bool(marque_corr)
    marque_est_modele = (not marque_reconnue) and bool(marque_brute and marque_brute.upper() in TOUS_MODELES)
    modele_est_marque = bool(modele_corr)

    if marque_reconnue and modele_est_marque:
        # Les deux sont des marques : garde marque, efface le modele en double
        donnees["marque"] = marque_corr
        donnees["modele"] = None

    elif marque_reconnue:
        # Cas normal : normalise l'orthographe de la marque
        donnees["marque"] = marque_corr

    elif modele_est_marque:
        if marque_est_modele:
            # marque contient un modele et modele contient la marque → inversion
            donnees["marque"] = modele_corr
            donnees["modele"] = marque_brute
        elif marque_brute is None:
            # marque vide, modele a la marque → déplace vers marque
            donnees["marque"] = modele_corr
            donnees["modele"] = None
        else:
            # marque non reconnue, modele a la marque → déplace la marque
            donnees["marque"] = modele_corr
            donnees["modele"] = None

    elif marque_est_modele:
        # marque est en fait un modele → déduit la marque via la table inverse
        marque_inferee = _MODELE_VERS_MARQUE.get(marque_brute.upper())
        donnees["marque"] = marque_inferee
        if modele_brut is None:
            donnees["modele"] = marque_brute

    else:
        # marque non reconnue : déduit depuis le modele si possible
        # La marque brute n'est pas dans le référentiel → l'inférence par modèle prime toujours
        mod = (donnees.get("modele") or "").upper()
        if mod:
            marque_inferee = _MODELE_VERS_MARQUE.get(mod)
            if marque_inferee:
                donnees["marque"] = marque_inferee

    # Supprime le préfixe marque dans modele si la dénomination l'inclut (ex: "NISSAN QASHQAI")
    marque_finale = donnees.get("marque")
    modele_final = donnees.get("modele")
    if marque_finale and modele_final:
        prefixe = marque_finale.upper()
        if modele_final.upper().startswith(prefixe):
            sans_prefixe = modele_final[len(prefixe):].strip(" -_")
            donnees["modele"] = sans_prefixe if len(sans_prefixe) >= 2 else None

    # Correction floue du modele contre la liste connue (ex: ARKAN→ARKANA)
    modele_a_corriger = donnees.get("modele")
    if modele_a_corriger and len(modele_a_corriger) >= 3 and modele_a_corriger.upper() not in TOUS_MODELES:
        resultats = get_close_matches(modele_a_corriger.upper(), TOUS_MODELES, n=1, cutoff=0.82)
        if not resultats:
            # Correction des confusions OCR courantes (0→O, 1→I) avant de réessayer
            corrected = modele_a_corriger.upper().replace("0", "O").replace("1", "I")
            if corrected != modele_a_corriger.upper():
                if corrected in TOUS_MODELES:
                    resultats = [corrected]
                else:
                    resultats = get_close_matches(corrected, TOUS_MODELES, n=1, cutoff=0.82)
        if resultats:
            donnees["modele"] = resultats[0]

    # Invalide le modele s'il n'appartient pas à la liste de référence
    modele_a_valider = donnees.get("modele")
    if modele_a_valider:
        modele_maj = modele_a_valider.upper()
        if modele_maj not in TOUS_MODELES:
            # Dénomination commerciale complexe (ex: "TIPO LIFE SEDAN") → extraire le modèle connu
            extrait = _extraire_modele_depuis_denomination(modele_a_valider)
            if extrait:
                modele_maj = extrait.upper()
                donnees["modele"] = extrait
            else:
                donnees["modele"] = None
        if modele_maj in TOUS_MODELES and marque_finale and score_marque >= 0.75:
            # Marque connue avec confiance : vérifie que le modele lui appartient
            modeles_marque = {m.upper() for m in _MODELES_BRUTS.get(marque_finale, [])}
            if modeles_marque and modele_maj not in modeles_marque:
                donnees["modele"] = None

    # Sécurité finale : efface toute marque absente du référentiel connu
    marque_fin = donnees.get("marque")
    if marque_fin and marque_approx(marque_fin) is None:
        donnees["marque"] = None
