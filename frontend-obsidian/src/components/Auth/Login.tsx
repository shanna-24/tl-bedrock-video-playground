/**
 * Login Component
 *
 * Provides a password input form with Obsidian Lens styling
 * for user authentication.
 *
 * Validates: Requirements 3.1, 3.2, 3.4
 */

import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

interface LoginProps {
  onLoginSuccess?: () => void;
}

export default function Login({ onLoginSuccess }: LoginProps) {
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login, error, isAuthenticated, clearError } = useAuth();

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Clear previous errors
    clearError();

    // Validate password is not empty
    if (!password.trim()) {
      return;
    }

    setIsLoading(true);

    try {
      // Call login function from useAuth hook
      await login(password);

      // Call success callback if provided
      if (onLoginSuccess) {
        onLoginSuccess();
      }

      // Navigation will happen automatically via useEffect when isAuthenticated changes
    } catch (err) {
      // Error is handled by useAuth hook
      console.error('Login error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        {/* Login Card */}
        <div className="bg-surface-container-high rounded-xl ghost-border p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-on-surface mb-2">
              TwelveLabs on AWS Bedrock
            </h1>
            <p className="text-on-surface-variant">
              Sign in to access your video archive
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Password Input */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-on-surface-variant mb-2"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                className="w-full px-4 py-3 bg-surface-container-low text-on-surface ghost-border rounded-lg
                         placeholder-on-surface-variant/50
                         focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-all duration-200"
                placeholder="Enter your password"
                autoComplete="current-password"
                autoFocus
              />
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-error-container/10 border border-error/30 rounded-lg p-3">
                <p className="text-error text-sm text-center font-medium">
                  {error}
                </p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 rounded-lg font-semibold
                       bg-gradient-to-r from-primary to-primary-container text-on-primary
                       hover:opacity-90
                       focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transform transition-all duration-200
                       hover:scale-[1.02] active:scale-[0.98]
                       shadow-lg hover:shadow-xl"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-on-primary"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Signing in...
                </span>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-on-surface-variant text-sm">
              Powered by TwelveLabs AI
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
