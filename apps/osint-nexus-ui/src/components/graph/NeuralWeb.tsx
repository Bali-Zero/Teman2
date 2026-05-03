'use client';

import { useEffect, useState, useMemo } from 'react';
import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import type { InstitutionDetail, OfficialData } from '@/lib/types';
import { OfficialNode } from './OfficialNode';
import { ConnectionLine } from './ConnectionLine';

function layoutNodes(officials: OfficialData[], width: number, height: number): { name: string; x: number; y: number }[] {
  const sorted = [...officials].sort((a, b) => b.total_assets - a.total_assets);
  const positions: { name: string; x: number; y: number }[] = [];
  const centerX = width / 2;
  const startY = 100;
  const spacing = 140;

  if (sorted.length > 0) {
    positions.push({ name: sorted[0].name, x: centerX, y: startY });
  }

  const remaining = sorted.slice(1);
  const rowSize = Math.max(3, Math.ceil(Math.sqrt(remaining.length)));

  remaining.forEach((official, i) => {
    const row = Math.floor(i / rowSize);
    const col = i % rowSize;
    const rowWidth = Math.min(rowSize, remaining.length - row * rowSize);
    const rowStartX = centerX - ((rowWidth - 1) * spacing) / 2;

    positions.push({
      name: official.name,
      x: rowStartX + col * spacing + (Math.random() - 0.5) * 20,
      y: startY + (row + 1) * 120 + (Math.random() - 0.5) * 15,
    });
  });

  return positions;
}

export function NeuralWeb() {
  const { state, dispatch } = useLevel();
  const institution = state.institution;
  const { data } = useNeo4j<InstitutionDetail>(
    institution ? `/api/graph/institution/${encodeURIComponent(institution)}` : null
  );

  const [viewSize, setViewSize] = useState({ width: 800, height: 600 });

  useEffect(() => {
    setViewSize({ width: window.innerWidth - 400, height: window.innerHeight - 100 });
  }, []);

  const positions = useMemo(() => {
    if (!data?.officials) return [];
    return layoutNodes(data.officials, viewSize.width, viewSize.height);
  }, [data, viewSize]);

  const posMap = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    positions.forEach((p) => m.set(p.name, { x: p.x, y: p.y }));
    return m;
  }, [positions]);

  if (!data) return null;

  return (
    <div className="absolute inset-0" style={{ zIndex: 30 }}>
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 29 }}>
        {data.relationships.map((rel, i) => {
          const from = posMap.get(rel.from);
          const to = posMap.get(rel.to);
          if (!from || !to) return null;
          return (
            <ConnectionLine
              key={`${rel.from}-${rel.to}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              type={rel.type}
              highlighted={
                state.selectedOfficial === rel.from ||
                state.selectedOfficial === rel.to
              }
              delay={800 + i * 50}
            />
          );
        })}
      </svg>

      {data.officials.map((official, i) => {
        const pos = posMap.get(official.name);
        if (!pos) return null;
        return (
          <OfficialNode
            key={official.name}
            official={official}
            x={pos.x}
            y={pos.y}
            selected={state.selectedOfficial === official.name}
            delay={400 + i * 80}
            onClick={() => dispatch({ type: 'SELECT_OFFICIAL', name: official.name })}
          />
        );
      })}
    </div>
  );
}
