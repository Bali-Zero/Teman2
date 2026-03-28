export default function Loading() {
  return (
    <div className="flex h-screen items-center justify-center bg-[#0c0c0e]">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-[#d4845a] border-t-transparent" />
        <p className="text-sm text-[#f1f1f1]/40">Caricamento Zantara...</p>
      </div>
    </div>
  );
}
