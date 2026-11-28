import { useQuery } from "@tanstack/react-query";

type Health = { status: string };

async function fetchHealth(url: string): Promise<Health> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

type Props = { name: string; url: string };

export function ServiceStatus({ name, url }: Props) {
  // TanStack Query tracks loading/error/data for us and caches by queryKey.
  // retry: false so a down service shows "unreachable" right away instead of
  // after three silent retries.
  const { data, isPending, isError } = useQuery({
    queryKey: ["health", url],
    queryFn: () => fetchHealth(url),
    retry: false,
  });

  let label: string;
  let color: string;
  if (isPending) {
    label = "checking…";
    color = "bg-gray-300";
  } else if (isError) {
    label = "unreachable";
    color = "bg-red-500";
  } else {
    label = data.status;
    color = data.status === "ok" ? "bg-green-500" : "bg-yellow-500";
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3">
      <span className="font-mono">{name}</span>
      <span className="flex items-center gap-2" data-testid={`status-${name}`}>
        <span className={`h-2.5 w-2.5 rounded-full ${color}`} aria-hidden="true" />
        {label}
      </span>
    </div>
  );
}
