export function PrimeMapSkeleton() {
  return (
    <div
      data-testid="prime-map-skeleton"
      className="absolute inset-0 bg-[#0c0c0e] overflow-hidden"
    >
      {/* Abstract topographic SVG — ~2KB inline, zero network */}
      <svg
        className="absolute inset-0 w-full h-full opacity-40"
        viewBox="0 0 800 600"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden
      >
        <defs>
          <radialGradient id="pm-ocean" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#1a2540" />
            <stop offset="100%" stopColor="#0c0c0e" />
          </radialGradient>
          <linearGradient id="pm-land" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#2d3e2a" />
            <stop offset="100%" stopColor="#1a1a1c" />
          </linearGradient>
        </defs>
        <rect width="800" height="600" fill="url(#pm-ocean)" />
        {/* Bali silhouette (stylized) */}
        <path
          d="M 180 260 Q 280 200 420 230 Q 560 250 640 290 Q 660 330 610 370 Q 520 410 380 400 Q 260 390 200 350 Q 150 310 180 260 Z"
          fill="url(#pm-land)"
          stroke="#d4845a"
          strokeWidth="0.5"
          strokeOpacity="0.3"
        />
        {/* Contour lines */}
        {[280, 300, 320, 340, 360].map((y, i) => (
          <path
            key={i}
            d={`M ${220 + i * 5} ${y} Q ${400 + i * 10} ${y - 20} ${580 - i * 5} ${y + 5}`}
            fill="none"
            stroke="#d4845a"
            strokeWidth="0.3"
            strokeOpacity="0.2"
          />
        ))}
      </svg>
      <div className="absolute inset-0 bg-gradient-to-b from-black/10 via-transparent to-black/60" />
      <div className="absolute inset-x-0 bottom-12 flex justify-center">
        <div className="px-4 py-2 rounded-full bg-black/60 text-white/80 text-sm backdrop-blur-md border border-white/10">
          Loading 3D map…
        </div>
      </div>
    </div>
  );
}
