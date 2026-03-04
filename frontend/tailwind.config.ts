import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // TwelveLabs Brand Colors
        'primary': '#6366F1',           // TwelveLabs Purple
        'primary-dark': '#4F46E5',      // TwelveLabs Purple Dark
        'primary-light': '#818CF8',     // TwelveLabs Purple Light
        'accent': '#22D3EE',            // TwelveLabs Cyan Accent
        'accent-dark': '#06B6D4',       // TwelveLabs Cyan Dark
        'accent-light': '#67E8F9',      // TwelveLabs Cyan Light
        // Override default lime colors for more subtle dark mode appearance
        'lime': {
          '50': '#f7fee7',
          '100': '#ecfccb',
          '200': '#d9f99d',
          '300': '#bef264',
          '400': '#4D7A12',              // Muted for dark mode
          '500': '#3D6410',              // Muted for dark mode  
          '600': '#325210',              // Muted for dark mode
          '700': '#2D4A0F',              // Muted for dark mode
          '800': '#1a2e05',
          '900': '#0f1f02',
          '950': '#0a1401',
        },
        // Dark mode accent (lime/green from TwelveLabs palette - muted for dark mode)
        'tl-lime': '#4A7A0D',           // TwelveLabs Lime (muted)
        'tl-lime-dark': '#3D6410',      // TwelveLabs Lime Dark (muted)
        'tl-lime-light': '#5C9411',     // TwelveLabs Lime Light
        // Neutral tones
        'tl-dark': '#0F172A',           // TwelveLabs Dark Background
        'tl-dark-secondary': '#1E293B', // TwelveLabs Dark Secondary
      },
      keyframes: {
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'tab-underline': {
          '0%': { transform: 'scaleX(0)' },
          '100%': { transform: 'scaleX(1)' },
        },
      },
      animation: {
        'slide-up': 'slide-up 0.3s ease-out forwards',
        'fade-in': 'fade-in 0.3s ease-out forwards',
        'shimmer': 'shimmer 2s linear infinite',
        'tab-underline': 'tab-underline 0.2s ease-out forwards',
      },
    },
  },
} satisfies Config
