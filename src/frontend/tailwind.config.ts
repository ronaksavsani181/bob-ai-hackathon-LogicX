/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Semiconductor-industrial design tokens
        sidebar: {
          DEFAULT: '#0f172a', // slate-900
          hover: '#1e293b',   // slate-800
          active: '#334155',  // slate-700
        },
        risk: {
          high: '#dc2626',    // red-600
          medium: '#d97706',  // amber-600
          low: '#16a34a',     // green-600
        },
      },
    },
  },
  plugins: [],
}
