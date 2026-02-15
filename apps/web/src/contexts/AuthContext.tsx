/**
 * Authentication Context for GATE Platform
 * 
 * Provides user authentication state and methods throughout the app.
 * Connects to /api/portal/* backend endpoints.
 */
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

// Types
export interface User {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    role: 'admin' | 'user' | 'readonly';
    client_id?: string;
    client_name?: string;
    status: string;
    last_login_at?: string;
}

export interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;
}

export interface AuthContextType extends AuthState {
    login: (email: string, password: string) => Promise<boolean>;
    logout: () => Promise<void>;
    checkAuth: () => Promise<void>;
    clearError: () => void;
}

// API base URL - empty string uses relative path (works with nginx proxy)
const API_BASE = import.meta.env.VITE_API_URL || '';

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token storage
const TOKEN_KEY = 'gate_session_token';

const getToken = (): string | null => {
    return localStorage.getItem(TOKEN_KEY);
};

const setToken = (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token);
};

const removeToken = (): void => {
    localStorage.removeItem(TOKEN_KEY);
};

// Provider component
export function AuthProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<AuthState>({
        user: null,
        isAuthenticated: false,
        isLoading: true,
        error: null,
    });

    // Check if user is authenticated on mount
    const checkAuth = useCallback(async () => {
        const token = getToken();
        if (!token) {
            setState(prev => ({ ...prev, isLoading: false, isAuthenticated: false }));
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/api/portal/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            if (response.ok) {
                const data = await response.json();
                setState({
                    user: data.user,
                    isAuthenticated: true,
                    isLoading: false,
                    error: null,
                });
            } else {
                // Token invalid, clear it
                removeToken();
                setState({
                    user: null,
                    isAuthenticated: false,
                    isLoading: false,
                    error: null,
                });
            }
        } catch (err) {
            console.error('Auth check failed:', err);
            setState({
                user: null,
                isAuthenticated: false,
                isLoading: false,
                error: null, // Don't show error for network issues on startup
            });
        }
    }, []);

    // Login function
    const login = useCallback(async (email: string, password: string): Promise<boolean> => {
        setState(prev => ({ ...prev, isLoading: true, error: null }));

        try {
            const response = await fetch(`${API_BASE}/api/portal/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password }),
            });

            const data = await response.json();

            if (response.ok) {
                setToken(data.session_token);
                setState({
                    user: data.user,
                    isAuthenticated: true,
                    isLoading: false,
                    error: null,
                });
                return true;
            } else {
                setState(prev => ({
                    ...prev,
                    isLoading: false,
                    error: data.detail || 'Login failed. Please check your credentials.',
                }));
                return false;
            }
        } catch (err) {
            console.error('Login error:', err);
            setState(prev => ({
                ...prev,
                isLoading: false,
                error: 'Network error. Please try again.',
            }));
            return false;
        }
    }, []);

    // Logout function
    const logout = useCallback(async () => {
        const token = getToken();

        if (token) {
            try {
                await fetch(`${API_BASE}/api/portal/logout`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                    },
                });
            } catch (err) {
                console.error('Logout error:', err);
            }
        }

        removeToken();
        setState({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
        });
    }, []);

    // Clear error
    const clearError = useCallback(() => {
        setState(prev => ({ ...prev, error: null }));
    }, []);

    // Check auth on mount
    useEffect(() => {
        checkAuth();
    }, [checkAuth]);

    const value: AuthContextType = {
        ...state,
        login,
        logout,
        checkAuth,
        clearError,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

// Hook to use auth context
export function useAuth(): AuthContextType {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

// Hook to get auth token for API calls
export function useAuthToken(): string | null {
    return getToken();
}

// Export token functions for API calls
export { getToken, setToken, removeToken };
