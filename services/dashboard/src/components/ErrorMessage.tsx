interface ErrorMessageProps {
  error: Error | null;
  title?: string;
}

export default function ErrorMessage({ error, title = 'Something went wrong' }: ErrorMessageProps) {
  if (!error) return null;
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
      <h3 className="text-sm font-semibold text-red-400">{title}</h3>
      <p className="mt-1 text-sm text-red-300">{error.message}</p>
    </div>
  );
}
