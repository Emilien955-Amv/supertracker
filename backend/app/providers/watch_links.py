"""Liens « regarder sur… » vers les plateformes de streaming.

Les données gratuites de TMDB/JustWatch ne donnent pas l'adresse exacte d'un
titre chez Netflix (JustWatch la réserve à son offre payante). On construit
donc un lien vers la RECHERCHE de la plateforme, avec le titre du contenu :
l'utilisateur arrive directement sur le bon résultat.

Pour une plateforme absente de cette liste, l'interface renvoie vers la page
TMDB qui récapitule toutes les offres (et redirige vers le bon titre).
"""

from urllib.parse import quote

# Nom de la plateforme chez TMDB (en minuscules) → modèle d'adresse de recherche.
# Uniquement des adresses vérifiées. Disney+, HBO Max, ADN ou Canal+ n'ont pas
# de page de recherche accessible par un lien : ils passent par la page des offres.
SEARCH_URLS = {
    "netflix": "https://www.netflix.com/search?q={q}",
    "amazon prime video": "https://www.primevideo.com/search?phrase={q}",
    "amazon video": "https://www.primevideo.com/search?phrase={q}",
    "apple tv": "https://tv.apple.com/fr/search?term={q}",
    "apple tv+": "https://tv.apple.com/fr/search?term={q}",
    "apple tv store": "https://tv.apple.com/fr/search?term={q}",
    "crunchyroll": "https://www.crunchyroll.com/fr/search?q={q}",
    "rakuten tv": "https://www.rakuten.tv/fr/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "google play movies": "https://play.google.com/store/search?q={q}&c=movies",
}


def search_url(provider_name: str, title: str) -> str | None:
    """Adresse de recherche du titre sur la plateforme, ou None si inconnue."""
    template = SEARCH_URLS.get(provider_name.strip().lower())
    # quote() encode espaces et accents (« Le Seigneur des anneaux » → Le%20Seigneur…).
    return template.format(q=quote(title, safe="")) if template else None
