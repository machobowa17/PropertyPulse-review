interface SparklineProps {
  data: { year: number; value: number }[];
  color?: string;
  width?: number;
  height?: number;
  className?: string;
}

/** Tiny inline SVG sparkline with trend-coloured end dot. No dependencies. */
export default function Sparkline({
  data,
  color = '#3b82f6',
  width = 120,
  height = 32,
  className = '',
}: SparklineProps) {
  if (!data || data.length < 2) return null;

  const values = data.map(d => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const padding = 2;
  const w = width - padding * 2;
  const h = height - padding * 2;

  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * w;
    const y = padding + h - ((d.value - min) / range) * h;
    return `${x},${y}`;
  });

  const lastVal = values[values.length - 1];
  const firstVal = values[0];
  const trending = lastVal > firstVal ? 'up' : lastVal < firstVal ? 'down' : 'flat';

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
    >
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={parseFloat(points[points.length - 1].split(',')[0])}
        cy={parseFloat(points[points.length - 1].split(',')[1])}
        r={2}
        fill={trending === 'up' ? '#22c55e' : trending === 'down' ? '#ef4444' : '#6b7280'}
      />
    </svg>
  );
}
