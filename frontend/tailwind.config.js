/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#070c16',
        panel: '#0d1524',
        panel2: '#111b2d',
        raised: '#16223a',
        line: '#1c2940',
        line2: '#2a3a57',
        ink: '#e6edf7',
        muted: '#93a4bd',
        dim: '#62728b',
        accent: { DEFAULT: '#22d3ee', soft: '#0b3340', ink: '#03202a' },
        ok: '#34d399',
        warn: '#fbbf24',
        bad: '#f87171',
        salmon: '#e8968c',
        teal: '#2b5c68',
        // legacy names (purane components bhi dark theme me theek dikhen)
        brand: { 50: '#0b3340', 100: '#0f4352', 500: '#22d3ee', 600: '#06b6d4', 700: '#67e8f9' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(34,211,238,.45), 0 0 28px rgba(34,211,238,.12)',
      },
    },
  },
  plugins: [],
}
