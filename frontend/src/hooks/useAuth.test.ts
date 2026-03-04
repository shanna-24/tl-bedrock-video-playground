/**
 * Unit tests for useAuth hook
 * 
 * Tests authentication state management, login/logout functionality,
 * and token persistence.
 * 
 * Note: These tests require Vitest and @testing-library/react to be installed.
 * Run: npm install -D vitest @testing-library/react @testing-library/react-hooks jsdom
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAuth } from './useAuth';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
  },
  getAuthToken: vi.fn(),
  removeAuthToken: vi.fn(),
  setAuthToken: vi.fn(),
  ApiError: class ApiError extends Error {
    statusCode: number;
    detail?: string;
    constructor(message: string, statusCode: number, detail?: string) {
      super(message);
      this.name = 'ApiError';
      this.statusCode = statusCode;
      this.detail = detail;
    }
  },
}));

describe('useAuth', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    vi.clearAllMocks();
    // Clear localStorage
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('should initialize with isAuthenticated=false when no token exists', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue(null);

      const { result } = renderHook(() => useAuth());

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for initialization to complete
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe(null);
    });

    it('should initialize with isAuthenticated=true when token exists', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue('valid-token');

      const { result } = renderHook(() => useAuth());

      // Wait for initialization to complete
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.error).toBe(null);
    });
  });

  describe('login', () => {
    it('should successfully login with correct password', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue(null);
      vi.mocked(api.authApi.login).mockResolvedValue({
        token: 'new-token',
        message: 'Login successful',
      });

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Perform login
      await act(async () => {
        await result.current.login('correct-password');
      });

      expect(api.authApi.login).toHaveBeenCalledWith('correct-password');
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.error).toBe(null);
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle login failure with ApiError', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue(null);
      const apiError = new api.ApiError(
        'Invalid password',
        401,
        'Invalid password'
      );
      vi.mocked(api.authApi.login).mockRejectedValue(apiError);

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Perform login
      await act(async () => {
        try {
          await result.current.login('wrong-password');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe('Invalid password');
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle login failure with generic error', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue(null);
      vi.mocked(api.authApi.login).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Perform login
      await act(async () => {
        try {
          await result.current.login('password');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe('Network error');
      expect(result.current.isLoading).toBe(false);
    });

    it('should clear previous errors on new login attempt', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue(null);
      
      // First login fails
      vi.mocked(api.authApi.login).mockRejectedValueOnce(
        new api.ApiError('Invalid password', 401, 'Invalid password')
      );

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // First login attempt
      await act(async () => {
        try {
          await result.current.login('wrong-password');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Invalid password');

      // Second login succeeds
      vi.mocked(api.authApi.login).mockResolvedValueOnce({
        token: 'new-token',
        message: 'Login successful',
      });

      await act(async () => {
        await result.current.login('correct-password');
      });

      expect(result.current.error).toBe(null);
      expect(result.current.isAuthenticated).toBe(true);
    });
  });

  describe('logout', () => {
    it('should successfully logout', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue('existing-token');
      vi.mocked(api.authApi.logout).mockResolvedValue({
        message: 'Logout successful',
      });

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);

      // Perform logout
      await act(async () => {
        await result.current.logout();
      });

      expect(api.authApi.logout).toHaveBeenCalled();
      expect(api.removeAuthToken).toHaveBeenCalled();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe(null);
      expect(result.current.isLoading).toBe(false);
    });

    it('should clear local state even if logout API fails', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue('existing-token');
      vi.mocked(api.authApi.logout).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);

      // Perform logout
      await act(async () => {
        await result.current.logout();
      });

      // Should still clear local state
      expect(api.removeAuthToken).toHaveBeenCalled();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe(null);
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('clearError', () => {
    it('should clear error state', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue(null);
      vi.mocked(api.authApi.login).mockRejectedValue(
        new api.ApiError('Invalid password', 401, 'Invalid password')
      );

      const { result } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Login fails
      await act(async () => {
        try {
          await result.current.login('wrong-password');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Invalid password');

      // Clear error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBe(null);
    });
  });

  describe('token persistence', () => {
    it('should maintain authentication state across hook re-renders', async () => {
      vi.mocked(api.getAuthToken).mockReturnValue('existing-token');

      const { result, rerender } = renderHook(() => useAuth());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);

      // Re-render the hook
      rerender();

      // Should still be authenticated
      expect(result.current.isAuthenticated).toBe(true);
    });
  });
});
