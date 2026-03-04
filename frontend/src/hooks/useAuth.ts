/**
 * useAuth Hook
 * 
 * Manages authentication state and provides login/logout functions.
 * Handles token persistence and authentication state across the application.
 * 
 * Validates: Requirements 5.1, 5.2, 5.3
 */

import { useAuthContext } from '../contexts/AuthContext';

export interface UseAuthReturn {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

/**
 * Custom hook for managing authentication state
 * 
 * @returns Authentication state and functions
 * 
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { isAuthenticated, login, logout, error } = useAuth();
 *   
 *   if (!isAuthenticated) {
 *     return <LoginForm onLogin={login} error={error} />;
 *   }
 *   
 *   return <Dashboard onLogout={logout} />;
 * }
 * ```
 */
export function useAuth(): UseAuthReturn {
  return useAuthContext();
}
