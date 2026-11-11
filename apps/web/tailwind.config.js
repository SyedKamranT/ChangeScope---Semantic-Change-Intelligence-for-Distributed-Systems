/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#ffffff',
        surface: '#ffffff',
        subtle: '#f8fafc',
        muted: '#f1f5f9',
        border: '#e2e8f0',
        'border-subtle': '#f1f5f9',
        ink: {
          primary: '#09090b',
          secondary: '#475569',
          muted: '#94a3b8',
        },
        primary: {
          DEFAULT: '#09090b',
          hover: '#27272a',
          accent: '#2563eb',
        },
        danger: {
          DEFAULT: '#dc2626',
          surface: '#fef2f2',
          border: '#fecaca',
          text: '#b91c1c',
        },
        warning: {
          DEFAULT: '#d97706',
          surface: '#fffbeb',
          border: '#fde68a',
          text: '#b45309',
        },
        success: {
          DEFAULT: '#059669',
          surface: '#ecfdf5',
          border: '#a7f3d0',
          text: '#047857',
        },
        info: {
          DEFAULT: '#0284c7',
          surface: '#f0f9ff',
          border: '#bae6fd',
          text: '#0369a1',
        },
      },
      boxShadow: {
        'premium': '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02)',
        'elevated': '0 4px 6px -1px rgba(0, 0, 0, 0.04), 0 2px 4px -2px rgba(0, 0, 0, 0.03), 0 0 0 1px rgba(0, 0, 0, 0.03)',
        'modal': '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.03), 0 0 0 1px rgba(0, 0, 0, 0.05)',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'ease-out-custom': 'cubic-bezier(0.23, 1, 0.32, 1)',
        'ease-in-out-custom': 'cubic-bezier(0.77, 0, 0.175, 1)',
      },
    },
  },
  plugins: [],
}
