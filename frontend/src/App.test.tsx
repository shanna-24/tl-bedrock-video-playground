/**
 * App Component Integration Tests
 * 
 * Tests for the main App component with routing.
 * 
 * Validates: Requirements 5.1
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';
import * as useAuthModule from './hooks/useAuth';

// Mock the useAuth hook
vi.mock('./hooks/useAuth');

describe('App Routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show login page when not authenticated', () => {
    // Mock unauthenticated state
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      clearError: vi.fn(),
    });

    render(<App />);

    // Should show login page
    expect(screen.getByText('TwelveLabs on AWS Bedrock')).toBeInTheDocument();
    expect(screen.getByText('Sign in to access your video archive')).toBeInTheDocument();
  });

  it('should show dashboard when authenticated', () => {
    // Mock authenticated state
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      clearError: vi.fn(),
    });

    render(<App />);

    // Should show dashboard
    expect(screen.getByText('TwelveLabs on AWS Bedrock')).toBeInTheDocument();
    expect(screen.getByText(/Welcome to your video archive/)).toBeInTheDocument();
    expect(screen.getByText('Sign Out')).toBeInTheDocument();
  });

  it('should show loading state while checking authentication', () => {
    // Mock loading state
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      clearError: vi.fn(),
    });

    render(<App />);

    // Should show loading indicator
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });
});
