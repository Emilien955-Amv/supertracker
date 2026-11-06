"""Titres de profil gagnés en complétant la collection d'une œuvre.

Certaines œuvres ont un titre à leur image ; les autres donnent « Maître de … ».
Pour en ajouter un : une ligne dans TITLES (mot-clé du titre → titre).
"""

import unicodedata

# Mot-clé cherché dans le titre de l'œuvre (minuscules, sans accents) → titre.
TITLES: tuple[tuple[str, str], ...] = (
    ("one piece", "Roi des pirates"),
    ("naruto", "Hokage"),
    ("boruto", "Hokage"),
    ("harry potter", "Grand sorcier"),
    ("dragon ball", "Super Saiyan"),
    ("pokemon", "Maître Pokémon"),
    ("star wars", "Maître Jedi"),
    ("seigneur des anneaux", "Porteur de l'Anneau"),
    ("lord of the rings", "Porteur de l'Anneau"),
    ("game of thrones", "Roi des Sept Couronnes"),
    ("attack on titan", "Soldat d'élite"),
    ("attaque des titans", "Soldat d'élite"),
    ("demon slayer", "Pourfendeur de démons"),
    ("my hero academia", "Héros n° 1"),
    ("jujutsu kaisen", "Exorciste de classe exceptionnelle"),
    ("black clover", "Empereur-Mage"),
    ("fairy tail", "Mage de rang S"),
    ("bleach", "Capitaine du Gotei 13"),
    ("hunter x hunter", "Hunter étoilé"),
    ("death note", "Kira"),
    ("breaking bad", "Heisenberg"),
    ("stranger things", "Gardien d'Hawkins"),
    ("avengers", "Avenger"),
    ("pirates des caraibes", "Capitaine pirate"),
    ("pirates of the caribbean", "Capitaine pirate"),
    ("hunger games", "Geai moqueur"),
    ("the witcher", "Sorceleur"),
)


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def title_for(work_title: str) -> str:
    """Titre de profil associé à une œuvre complétée."""
    plain = _plain(work_title)
    for keyword, title in TITLES:
        if keyword in plain:
            return title
    return f"Maître de {work_title}"
