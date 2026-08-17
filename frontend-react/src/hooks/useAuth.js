import { useState, useEffect, useCallback } from 'react';
import { login as apiLogin, logout as apiLogout, isAuthenticated, initAuth, getProfile } from '../api';

export function useAuth() {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  useEffect(() => {
    initAuth();
    if (isAuthenticated()) {
      setAuthenticated(true);
      checkProfile();
    } else {
      setLoading(false);
    }
  }, []);

  const checkProfile = async () => {
    try {
      await getProfile();
      setNeedsOnboarding(false);
    } catch (e) {
      setNeedsOnboarding(true);
    } finally {
      setLoading(false);
    }
  };

  const login = useCallback(async (username, password) => {
    await apiLogin(username, password);
    setAuthenticated(true);
    setLoading(true);
    await checkProfile();
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setAuthenticated(false);
    setNeedsOnboarding(false);
  }, []);

  const completeOnboarding = useCallback(() => {
    setNeedsOnboarding(false);
  }, []);

  return {
    authenticated,
    loading,
    needsOnboarding,
    login,
    logout,
    completeOnboarding,
  };
}
