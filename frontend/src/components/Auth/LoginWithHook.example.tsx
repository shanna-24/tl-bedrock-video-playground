/**
 * Login Component (Alternative Implementation using useAuth hook)
 * 
 * This is an example showing how the Login component could be refactored
 * to use the useAuth hook instead of managing state directly.
 * 
 * This file is for reference only and is not used in the application.
 * The actual Login.tsx component works independently without the hook.
 */

import { useState, type FormEvent } from 'react';
import { useAuth } from '../../hooks/useAuth';

interface LoginProps {
  onLoginSuccess?: () => void;
}

export default function LoginWithHook({ onLoginSuccess }: LoginProps) {
  const [password, setPassword] = useState('');
  const { login, error, isLoading } = useAuth();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    // Validate password is not empty
    if (!password.trim()) {
      return;
    }

    try {
      // Use the hook's login function
      await login(password);
      
      // Call success callback if provided
      if (onLoginSuccess) {
        onLoginSuccess();
      }
    } catch (err) {
      // Error is already handled by the hook and available in the error state
      console.error('Login failed:', err);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-white to-gray-600 p-4">
      <div className="w-full max-w-md">
        {/* Login Card */}
        <div className="bg-gray-50 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-gray-200">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              TwelveLabs on AWS Bedrock
            </h1>
            <p className="text-gray-600">
              Sign in to access your video archive
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Password Input */}
            <div>
              <label 
                htmlFor="password" 
                className="block text-sm font-medium text-gray-200 mb-2"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                className="w-full px-4 py-3 bg-white border border-gray-200 shadow-sm rounded-lg 
                         text-gray-900 placeholder-gray-400 
                         focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-transparent
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-all duration-200"
                placeholder="Enter your password"
                autoComplete="current-password"
                autoFocus
              />
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3">
                <p className="text-red-200 text-sm text-center">
                  {error}
                </p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 rounded-lg font-semibold text-white
                       bg-indigo-600
                       hover:bg-indigo-700
                       focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-2 focus:ring-offset-gray-900
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transform transition-all duration-200
                       hover:scale-[1.02] active:scale-[0.98]
                       shadow-lg hover:shadow-xl"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <svg 
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-900" 
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
            <p className="text-gray-500 text-sm">
              Powered by TwelveLabs AI
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
