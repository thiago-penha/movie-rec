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
    </main>
  );
}
