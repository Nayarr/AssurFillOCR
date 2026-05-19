"""
Décodage local d'un VIN (ISO 3779) sans appel réseau.
Extrait la marque depuis le WMI (3 premiers caractères).
"""

_WMI = {
    # France
    'VF1': 'RENAULT', 'VF2': 'RENAULT', 'VF3': 'PEUGEOT', 'VF6': 'RENAULT',
    'VF7': 'CITROËN', 'VF8': 'CITROËN', 'VFA': 'RENAULT', 'VFB': 'CITROËN',
    'VFC': 'CITROËN', 'VFE': 'PEUGEOT', 'VFF': 'PEUGEOT', 'VFG': 'PEUGEOT',
    'VFJ': 'RENAULT', 'VFK': 'CITROËN', 'VFL': 'RENAULT', 'VFM': 'CITROËN',
    'VFN': 'OPEL',    'VFP': 'PEUGEOT',
    # Espagne
    'VSS': 'SEAT', 'VSA': 'SEAT', 'VSE': 'SEAT', 'VSX': 'OPEL',
    'VNK': 'TOYOTA', 'VNE': 'NISSAN',
    # Italie
    'ZAR': 'ALFA ROMEO', 'ZFA': 'FIAT', 'ZFB': 'FIAT', 'ZFC': 'FIAT',
    'ZFD': 'FIAT',    'ZFE': 'FIAT',  'ZFH': 'FIAT',  'ZFF': 'FERRARI',
    'ZDF': 'FERRARI', 'ZBB': 'FERRARI', 'ZHW': 'LAMBORGHINI',
    'ZCF': 'IVECO',   'ZGA': 'LANCIA',  'ZAP': 'PIAGGIO',
    # Allemagne
    'WBA': 'BMW', 'WBB': 'BMW', 'WBY': 'BMW', 'WBX': 'BMW',
    'WDB': 'MERCEDES', 'WDC': 'MERCEDES', 'WDD': 'MERCEDES', 'WDF': 'MERCEDES',
    'WEB': 'MERCEDES', 'WME': 'SMART',
    'WVW': 'VOLKSWAGEN', 'WV1': 'VOLKSWAGEN', 'WV2': 'VOLKSWAGEN',
    'WAU': 'AUDI',    'WAG': 'AUDI',
    'WP0': 'PORSCHE', 'WP1': 'PORSCHE',
    'WMA': 'MAN',
    # Royaume-Uni
    'SAJ': 'JAGUAR', 'SAL': 'LAND ROVER', 'SAR': 'ROVER',
    # Suède
    'YV1': 'VOLVO', 'YV2': 'VOLVO', 'YV4': 'VOLVO',
    'YS2': 'SCANIA', 'YS3': 'SAAB',
    # Japon
    'JHM': 'HONDA', 'JN1': 'NISSAN', 'JN6': 'NISSAN',
    'JT2': 'TOYOTA', 'JT3': 'TOYOTA', 'JTD': 'TOYOTA',
    'JS1': 'SUZUKI', 'JS2': 'SUZUKI',
    # Corée
    'KNA': 'KIA', 'KND': 'KIA',
    'KMH': 'HYUNDAI', 'KMJ': 'HYUNDAI',
    # USA
    '1FA': 'FORD', '1FB': 'FORD', '1FC': 'FORD', '1FT': 'FORD',
    '1G1': 'CHEVROLET', '1G6': 'CADILLAC',
    '1HG': 'HONDA', '1N4': 'NISSAN',
    '2T1': 'TOYOTA', '4T1': 'TOYOTA',
    'JA3': 'MITSUBISHI', 'JA4': 'MITSUBISHI',
}


def decode_marque(vin: str) -> str | None:
    """Retourne la marque déduite du WMI, ou None si inconnu."""
    if not vin or len(vin) != 17:
        return None
    return _WMI.get(vin[:3].upper())
