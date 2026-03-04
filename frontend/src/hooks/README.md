# React Hooks

This directory contains custom React hooks for the TL-Video-Playground application.

## useAuth

The `useAuth` hook manages authentication state and provides login/logout functionality.

### Usage

```tsx
import { useAuth } from './hooks/useAuth';

function App() {
  const { isAuthenticated, isLoading, error, login, logout, clearError } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div>
        <h1>Please login</h1>
        {error && <p className="error">{error}</p>}
        <button onClick={() => login('my-password')}>
          Login
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1>Welcome!</h1>
      <button onClick={logout}>Logout</button>
    </div>
  );
}
```

### API

#### State

- `isAuthenticated: boolean` - Whether the user is currently authenticated
- `isLoading: boolean` - Whether an authentication operation is in progress
- `error: string | null` - Error message from the last failed operation

#### Functions

- `login(password: string): Promise<void>` - Authenticate with password
- `logout(): Promise<void>` - Log out the current user
- `clearError(): void` - Clear the error state

### Features

- **Token Persistence**: Authentication tokens are stored in localStorage and persist across page reloads
- **Automatic Initialization**: Checks for existing tokens on mount
- **Error Handling**: Provides user-friendly error messages
- **Loading States**: Tracks loading state during async operations

### Testing

Run tests with:

```bash
npm test
```

Note: Requires Vitest and React Testing Library to be installed:

```bash
npm install -D vitest @testing-library/react @testing-library/react-hooks jsdom
```

Then add to `package.json`:

```json
{
  "scripts": {
    "test": "vitest"
  }
}
```

And create `vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
});
```
