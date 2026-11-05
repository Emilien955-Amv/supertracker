/** Mention exigée par les conditions d'utilisation de TMDB. */
export function Attribution() {
  return (
    <p className="mt-8 text-center text-xs text-muted">
      Données fournies par{" "}
      <a href="https://www.themoviedb.org" className="underline" target="_blank" rel="noreferrer">
        TMDB
      </a>{" "}
      et{" "}
      <a href="https://anilist.co" className="underline" target="_blank" rel="noreferrer">
        AniList
      </a>
      . Ce produit utilise l'API TMDB mais n'est ni approuvé ni certifié par TMDB.
    </p>
  );
}
