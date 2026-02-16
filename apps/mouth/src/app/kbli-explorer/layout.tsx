import React from "react";

export default function KBLIExplorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-screen w-full bg-[#050507] text-[#E1E1E3] overflow-hidden overflow-x-hidden font-sans selection:bg-[#D4B483]/30 selection:text-[#D4B483]">
      {/* Texture Layer: Noise/Grain for tactile feel */}
      <div
        className="fixed inset-0 z-0 opacity-[0.03] pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage:
            'url("https://grainy-gradients.vercel.app/noise.svg")',
        }}
      />

      {/* Ambient Lighting: Subtle, deep, atmospheric */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[20%] w-[40%] h-[40%] bg-[#D4B483]/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-10%] right-[10%] w-[30%] h-[40%] bg-[#2A3241]/10 rounded-full blur-[120px]" />
      </div>

      {/* Main Content Layer */}
      <div className="relative z-10 h-full flex flex-col">{children}</div>
    </div>
  );
}
