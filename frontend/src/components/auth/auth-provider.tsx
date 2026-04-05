"use client";

import { createContext, ReactNode, useContext, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, fetchCsrfCookie, fetchCurrentUser, logoutUser } from "@/lib/api";
import { UserProfile } from "@/lib/types";

const AUTH_QUERY_KEY = ["auth", "me"];

type AuthContextValue = {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuthenticatedUser: (user: UserProfile | null) => void;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: async () => {
      await fetchCsrfCookie();
      return fetchCurrentUser();
    },
    retry: false,
  });

  const authError = sessionQuery.error instanceof ApiError ? sessionQuery.error : null;
  const isAuthenticated = Boolean(sessionQuery.data);
  const isUnauthenticated = authError ? [401, 403].includes(authError.status) : false;

  const value = useMemo<AuthContextValue>(
    () => ({
      user: sessionQuery.data ?? null,
      isAuthenticated,
      isLoading: sessionQuery.isLoading,
      setAuthenticatedUser: (user) => {
        queryClient.setQueryData(AUTH_QUERY_KEY, user);
      },
      refreshSession: async () => {
        await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      },
      logout: async () => {
        await logoutUser();
        queryClient.setQueryData(AUTH_QUERY_KEY, null);
        await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      },
    }),
    [isAuthenticated, queryClient, sessionQuery.data, sessionQuery.isLoading],
  );

  return (
    <AuthContext.Provider
      value={{
        ...value,
        user: isUnauthenticated ? null : value.user,
        isAuthenticated: isUnauthenticated ? false : value.isAuthenticated,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
