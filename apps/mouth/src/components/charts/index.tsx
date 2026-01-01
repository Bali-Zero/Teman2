'use client';

import React from 'react';
import { ResponsiveLine } from '@nivo/line';
import { ResponsiveBar } from '@nivo/bar';
import { ResponsivePie } from '@nivo/pie';

// Dark theme for Nivo charts matching our design system
const darkTheme = {
  background: 'transparent',
  textColor: '#b8b8b8',
  fontSize: 11,
  axis: {
    domain: {
      line: {
        stroke: '#2e2e2e',
        strokeWidth: 1,
      },
    },
    ticks: {
      line: {
        stroke: '#2e2e2e',
        strokeWidth: 1,
      },
      text: {
        fill: '#737373',
        fontSize: 10,
      },
    },
    legend: {
      text: {
        fill: '#b8b8b8',
        fontSize: 11,
      },
    },
  },
  grid: {
    line: {
      stroke: '#2e2e2e',
      strokeWidth: 1,
    },
  },
  legends: {
    text: {
      fill: '#b8b8b8',
      fontSize: 11,
    },
  },
  tooltip: {
    container: {
      background: '#212121',
      color: '#f5f5f5',
      fontSize: 12,
      borderRadius: 8,
      boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
      border: '1px solid #2e2e2e',
    },
  },
};

// Accent colors for charts
const chartColors = [
  '#6366f1', // accent (indigo)
  '#22c55e', // success (green)
  '#f59e0b', // warning (amber)
  '#3b82f6', // info (blue)
  '#ec4899', // pink
  '#8b5cf6', // purple
  '#14b8a6', // teal
  '#f97316', // orange
];

interface LineChartProps {
  data: Array<{
    id: string;
    data: Array<{ x: string | number; y: number }>;
  }>;
  height?: number;
  enableArea?: boolean;
  curve?: 'linear' | 'monotoneX' | 'natural' | 'step';
}

export function LineChart({
  data,
  height = 200,
  enableArea = true,
  curve = 'monotoneX',
}: LineChartProps) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-[var(--foreground-muted)]">
        No data available
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveLine
        data={data}
        theme={darkTheme}
        colors={chartColors}
        margin={{ top: 20, right: 20, bottom: 40, left: 50 }}
        xScale={{ type: 'point' }}
        yScale={{ type: 'linear', min: 'auto', max: 'auto', stacked: false }}
        curve={curve}
        axisTop={null}
        axisRight={null}
        axisBottom={{
          tickSize: 5,
          tickPadding: 5,
          tickRotation: -45,
        }}
        axisLeft={{
          tickSize: 5,
          tickPadding: 5,
          tickRotation: 0,
        }}
        enablePoints={true}
        pointSize={6}
        pointColor={{ theme: 'background' }}
        pointBorderWidth={2}
        pointBorderColor={{ from: 'serieColor' }}
        enableArea={enableArea}
        areaOpacity={0.15}
        useMesh={true}
        animate={true}
        motionConfig="gentle"
      />
    </div>
  );
}

interface BarChartProps {
  data: Array<Record<string, string | number>>;
  keys: string[];
  indexBy: string;
  height?: number;
  layout?: 'vertical' | 'horizontal';
  groupMode?: 'grouped' | 'stacked';
}

export function BarChart({
  data,
  keys,
  indexBy,
  height = 200,
  layout = 'vertical',
  groupMode = 'grouped',
}: BarChartProps) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-[var(--foreground-muted)]">
        No data available
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveBar
        data={data}
        keys={keys}
        indexBy={indexBy}
        theme={darkTheme}
        colors={chartColors}
        margin={{ top: 20, right: 20, bottom: 50, left: 60 }}
        padding={0.3}
        layout={layout}
        groupMode={groupMode}
        valueScale={{ type: 'linear' }}
        indexScale={{ type: 'band', round: true }}
        borderRadius={4}
        borderColor={{ from: 'color', modifiers: [['darker', 1.6]] }}
        axisTop={null}
        axisRight={null}
        axisBottom={{
          tickSize: 5,
          tickPadding: 5,
          tickRotation: -45,
        }}
        axisLeft={{
          tickSize: 5,
          tickPadding: 5,
          tickRotation: 0,
        }}
        labelSkipWidth={12}
        labelSkipHeight={12}
        labelTextColor={{ from: 'color', modifiers: [['darker', 3]] }}
        animate={true}
        motionConfig="gentle"
      />
    </div>
  );
}

interface PieChartProps {
  data: Array<{ id: string; label: string; value: number; color?: string }>;
  height?: number;
  innerRadius?: number;
  enableArcLabels?: boolean;
}

export function PieChart({
  data,
  height = 200,
  innerRadius = 0.5,
  enableArcLabels = true,
}: PieChartProps) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-[var(--foreground-muted)]">
        No data available
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsivePie
        data={data}
        theme={darkTheme}
        colors={chartColors}
        margin={{ top: 20, right: 80, bottom: 20, left: 80 }}
        innerRadius={innerRadius}
        padAngle={0.7}
        cornerRadius={4}
        activeOuterRadiusOffset={8}
        borderWidth={1}
        borderColor={{ from: 'color', modifiers: [['darker', 0.2]] }}
        arcLinkLabelsSkipAngle={10}
        arcLinkLabelsTextColor="#b8b8b8"
        arcLinkLabelsThickness={2}
        arcLinkLabelsColor={{ from: 'color' }}
        arcLabelsSkipAngle={10}
        arcLabelsTextColor={{ from: 'color', modifiers: [['darker', 3]] }}
        enableArcLabels={enableArcLabels}
        animate={true}
        motionConfig="gentle"
      />
    </div>
  );
}

// Mini sparkline chart for inline stats
interface SparklineProps {
  data: number[];
  height?: number;
  color?: string;
}

export function Sparkline({ data, height = 40, color = '#6366f1' }: SparklineProps) {
  if (!data || data.length === 0) return null;

  const lineData = [
    {
      id: 'sparkline',
      data: data.map((y, x) => ({ x: x.toString(), y })),
    },
  ];

  return (
    <div style={{ height, width: '100%' }}>
      <ResponsiveLine
        data={lineData}
        colors={[color]}
        margin={{ top: 5, right: 5, bottom: 5, left: 5 }}
        xScale={{ type: 'point' }}
        yScale={{ type: 'linear', min: 'auto', max: 'auto' }}
        curve="monotoneX"
        axisTop={null}
        axisRight={null}
        axisBottom={null}
        axisLeft={null}
        enableGridX={false}
        enableGridY={false}
        enablePoints={false}
        enableArea={true}
        areaOpacity={0.2}
        isInteractive={false}
        animate={true}
        motionConfig="gentle"
      />
    </div>
  );
}

export default { LineChart, BarChart, PieChart, Sparkline };
