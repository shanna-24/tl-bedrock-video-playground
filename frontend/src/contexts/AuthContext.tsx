/**
 * AuthContext
 * 
 * Provides authentication state and functions throughout the application.
 * Ensures consistent authentication state across all components.
 * 
 * Validates: Requirements 5.1, 5.2, 5.3
 */

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { authApi, getAuthToken, removeAuthToken, ApiError } from '../services/api';

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  /**
   * Check if user is already authenticated on mount
   */
  useEffect(() => {
    const checkAuth = () => {
      const token = getAuthToken();
      setState({
        isAuthenticated: !!token,
        isLoading: false,
        error: null,
      });
    };

    checkAuth();
  }, []);

  /**
   * Login with password
   */
  const login = useCallback(async (password: string) => {
    setState(prev => ({ ...prev, error: null, isLoading: true }));

    try {
      await authApi.login(password);
      
      setState({
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      let errorMessage = 'An unexpected error occurred. Please try again.';
      
      if (err instanceof ApiError) {
        errorMessage = err.detail || errorMessage;
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      setState({
        isAuthenticated: false,
        isLoading: false,
        error: errorMessage,
      });

      throw err;
    }
  }, []);

  /**
   * Logout current user
   */
  const logout = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true }));

    try {
      await authApi.logout();
    } catch (err) {
      console.error('Logout API error:', err);
    } finally {
      removeAuthToken();
      setState({
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, []);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth context
 */
export function useAuthContext() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}
