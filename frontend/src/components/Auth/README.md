# Authentication Components

This directory contains authentication-related components for the TL Video Playground application.

## Components

### Login.tsx

The login component provides a password input form with green/purple gradient styling for user authentication.

**Features:**
- Password input with validation
- Error handling and display
- Loading state during authentication
- Automatic redirect to dashboard on successful login
- Integration with `useAuth` hook

**Usage:**
```tsx
import Login from './components/Auth/Login';

<Route path="/login" element={<Login />} />
```

### ProtectedRoute.tsx

A wrapper component that protects routes requiring authentication. It redirects unauthenticated users to the login page.

**Features:**
- Checks authentication status using `useAuth` hook
- Shows loading state while checking authentication
- Redirects to `/login` if not authenticated
- Renders children if authenticated

**Usage:**
```tsx
import ProtectedRoute from './components/Auth/ProtectedRoute';

<Route 
  path="/dashboard" 
  element={
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  } 
/>
```

## Routing Setup

The application uses React Router for navigation with the following routes:

- `/login` - Login page (public)
- `/` - Dashboard (protected, requires authentication)
- `*` - Catch-all redirects to `/`

### Authentication Flow

1. User visits the application
2. `ProtectedRoute` checks authentication status via `useAuth` hook
3. If loading, shows loading spinner
4. If not authenticated, redirects to `/login`
5. If authenticated, renders the protected content
6. After successful login, user is redirected to `/`

### Example App Setup

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Auth/Login';
import ProtectedRoute from './components/Auth/ProtectedRoute';
import Dashboard from './components/Dashboard/Dashboard';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route 
          path="/" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

## Testing

Both components have comprehensive test coverage:

- `Login.test.tsx` - Tests login form functionality
- `ProtectedRoute.test.tsx` - Tests route protection logic
- `App.test.tsx` - Integration tests for routing

Run tests with:
```bash
npm test
```

## Requirements Validation

These components validate the following requirements:

- **Requirement 5.1**: Authentication required to access the system
- **Requirement 5.2**: Correct credentials grant access
- **Requirement 5.3**: Incorrect credentials deny access with error message
- **Requirement 8.4**: Green/purple gradient color scheme
