import { ServiceStatus } from "./components/ServiceStatus.tsx";

export default function App() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-8 px-4 py-16">
      <h1 className="text-4xl font-bold tracking-tight">CineMatch</h1>
      <section aria-labelledby="status-heading" className="flex flex-col gap-3">
        <h2 id="status-heading" className="text-lg font-semibold">
          Service status
        </h2>
        <ServiceStatus name="api" url="/api/health" />
        <ServiceStatus name="recommender" url="/rec/health" />
      </section>
      {/* Required by TMDB's terms of use (spec §4). The logo arrives with the real UI (Phase 5). */}
      <footer className="mt-auto border-t border-gray-200 pt-4 text-sm text-gray-500">
        Movie data from{" "}
        <a href="https://www.themoviedb.org/" className="underline" target="_blank" rel="noreferrer">
          TMDB
        </a>
        . This product uses the TMDB API but is not endorsed or certified by TMDB.
      </footer>
    </main>
  );
}
