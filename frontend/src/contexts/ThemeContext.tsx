/**
 * ThemeContext
 * 
 * Provides theme state and functions throughout the application.
 * Manages light/dark mode with localStorage persistence and config defaults.
 */

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

type ThemeMode = 'light' | 'dark';

interface ThemeContextValue {
  mode: ThemeMode;
  toggleTheme: () => void;
  setTheme: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [mode, setMode] = useState<ThemeMode>('light');

  // Initialize theme from localStorage or fetch from config
  useEffect(() => {
    const initializeTheme = async () => {
      // Check localStorage first
      const savedTheme = localStorage.getItem('theme') as ThemeMode | null;
      
      if (savedTheme && (savedTheme === 'light' || savedTheme === 'dark')) {
        setMode(savedTheme);
        applyTheme(savedTheme);
      } else {
        // Fetch default from backend config
        try {
          const response = await fetch('/api/config/theme');
          
          if (response.ok) {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
              const data = await response.json();
              const defaultMode = data.default_mode as ThemeMode;
              setMode(defaultMode);
              applyTheme(defaultMode);
            } else {
              applyTheme('light');
            }
          } else {
            // Fallback to light mode if fetch fails
            applyTheme('light');
          }
        } catch (error) {
          console.error('Failed to fetch theme config:', error);
          // Fallback to light mode
          applyTheme('light');
        }
      }
    };

    initializeTheme();
  }, []);

  const applyTheme = (theme: ThemeMode) => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      document.body.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.body.classList.remove('dark');
    }
  };

  const setTheme = (newMode: ThemeMode) => {
    setMode(newMode);
    localStorage.setItem('theme', newMode);
    applyTheme(newMode);
  };

  const toggleTheme = () => {
    const newMode = mode === 'light' ? 'dark' : 'light';
    setTheme(newMode);
  };

  return (
    <ThemeContext.Provider value={{ mode, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
