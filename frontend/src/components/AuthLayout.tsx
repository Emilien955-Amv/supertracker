import type { ReactNode } from "react";

/** Mise en page commune aux écrans de connexion et d'inscription. */
export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-8 px-5 py-10">
      <header className="text-center">
        <img src="/icon.svg" alt="" className="mx-auto h-16 w-16" />
        <h1 className="mt-4 text-3xl font-bold">{title}</h1>
        <p className="mt-2 text-muted">{subtitle}</p>
      </header>
      <div className="rounded-2xl border border-border bg-surface p-6">{children}</div>
    </main>
  );
}
