import { useEffect, useState } from "react";
import { Link } from "react-router";

import { Avatar } from "../components/Avatar";
import { FriendButton } from "../components/FriendButton";
import { apiFetch } from "../lib/api";
import type { Friends, PublicUser, Relation } from "../lib/social";
import { useApiResource, useDebouncedValue } from "../lib/useApi";

/** Mes amis : recherche d'utilisateurs, demandes reçues et envoyées, liste. */
export default function FriendsPage() {
  const [state, setFriends] = useApiResource<Friends>("/api/friends");
  const [search, setSearch] = useState("");
  const query = useDebouncedValue(search.trim(), 300);
  const [results, setResults] = useState<PublicUser[] | null>(null);

  useEffect(() => {
    if (query.length < 2) {
      setResults(null);
      return;
    }
    const controller = new AbortController();
    apiFetch<PublicUser[]>(`/api/users/search?q=${encodeURIComponent(query)}`, {
      signal: controller.signal,
    })
      .then(setResults)
      .catch(() => {
        if (!controller.signal.aborted) setResults([]);
      });
    return () => controller.abort();
  }, [query]);

  async function reload() {
    setFriends(await apiFetch<Friends>("/api/friends"));
  }

  function changed(username: string, relation: Relation) {
    setResults((list) => list?.map((u) => (u.username === username ? { ...u, relation } : u)) ?? null);
    void reload();
  }

  const friends = state.status === "success" ? state.data : null;

  return (
    <main className="mx-auto max-w-3xl px-5 pt-8">
      <Link to="/profil" className="text-sm text-muted hover:text-text">
        ← Mon profil
      </Link>
      <h1 className="mt-3 text-2xl font-bold">Mes amis</h1>

      <label className="mt-4 block">
        <span className="sr-only">Chercher un utilisateur par pseudo</span>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          maxLength={30}
          placeholder="Chercher un pseudo…"
          className="block w-full rounded-xl border border-border bg-surface px-4 py-2.5"
        />
      </label>
      {results !== null && (
        <section aria-label="Résultats de la recherche" className="mt-3">
          {results.length === 0 ? (
            <p className="text-sm text-muted">Aucun utilisateur trouvé.</p>
          ) : (
            <UserList users={results} onChange={changed} />
          )}
        </section>
      )}

      {state.status === "error" && (
        <p role="alert" className="mt-4 text-error">
          {state.error.message}
        </p>
      )}
      {friends && (
        <>
          {friends.incoming.length > 0 && (
            <section aria-labelledby="recues" className="mt-6">
              <h2 id="recues" className="font-semibold">
                Demandes reçues ({friends.incoming.length})
              </h2>
              <UserList users={friends.incoming} onChange={changed} withDecline />
            </section>
          )}
          <section aria-labelledby="amis" className="mt-6">
            <h2 id="amis" className="font-semibold">
              Amis ({friends.friends.length})
            </h2>
            {friends.friends.length === 0 ? (
              <p className="mt-2 text-sm text-muted">
                Cherchez le pseudo d'un ami ci-dessus pour lui envoyer une demande.
              </p>
            ) : (
              <UserList users={friends.friends} onChange={changed} />
            )}
          </section>
          {friends.outgoing.length > 0 && (
            <section aria-labelledby="envoyees" className="mt-6">
              <h2 id="envoyees" className="font-semibold text-muted">
                Demandes envoyées ({friends.outgoing.length})
              </h2>
              <UserList users={friends.outgoing} onChange={changed} />
            </section>
          )}
        </>
      )}
    </main>
  );
}

function UserList({
  users,
  onChange,
  withDecline = false,
}: {
  users: PublicUser[];
  onChange: (username: string, relation: Relation) => void;
  withDecline?: boolean;
}) {
  return (
    <ul className="mt-2 divide-y divide-border rounded-xl border border-border bg-surface">
      {users.map((user) => (
        <li key={user.username} className="flex items-center gap-3 p-3">
          <Avatar username={user.username} />
          <Link
            to={`/u/${encodeURIComponent(user.username)}`}
            className="min-w-0 flex-1 truncate font-medium hover:underline"
          >
            {user.username}
          </Link>
          <FriendButton
            username={user.username}
            relation={user.relation}
            onChange={(relation) => onChange(user.username, relation)}
          />
          {withDecline && (
            <button
              type="button"
              aria-label={`Refuser la demande : ${user.username}`}
              onClick={() =>
                void apiFetch<void>(`/api/friends/${encodeURIComponent(user.username)}`, {
                  method: "DELETE",
                }).then(() => onChange(user.username, "none"))
              }
              className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-bg"
            >
              Refuser
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
