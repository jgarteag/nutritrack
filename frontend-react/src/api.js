const API_URL = import.meta.env.VITE_API_URL;
const COGNITO_POOL_ID = import.meta.env.VITE_COGNITO_POOL_ID;
const COGNITO_CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;
const REGION = import.meta.env.VITE_REGION;

const COGNITO_ENDPOINT = `https://cognito-idp.${REGION}.amazonaws.com/`;

// --- Auth Functions ---

export async function login(username, password) {
  const response = await fetch(COGNITO_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    },
    body: JSON.stringify({
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: COGNITO_CLIENT_ID,
      AuthParameters: {
        USERNAME: username,
        PASSWORD: password,
      },
    }),
  });

  const data = await response.json();

  if (data.__type) {
    throw new Error(data.message || 'Error de autenticación');
  }

  const result = data.AuthenticationResult;
  const expiresAt = Date.now() + result.ExpiresIn * 1000;

  sessionStorage.setItem('accessToken', result.AccessToken);
  sessionStorage.setItem('idToken', result.IdToken);
  sessionStorage.setItem('refreshToken', result.RefreshToken);
  sessionStorage.setItem('tokenExpiresAt', expiresAt.toString());

  scheduleTokenRefresh(result.ExpiresIn);

  return result;
}

export function logout() {
  sessionStorage.removeItem('accessToken');
  sessionStorage.removeItem('idToken');
  sessionStorage.removeItem('refreshToken');
  sessionStorage.removeItem('tokenExpiresAt');
}

export function getAccessToken() {
  return sessionStorage.getItem('accessToken');
}

export function isAuthenticated() {
  const token = getAccessToken();
  const expiresAt = sessionStorage.getItem('tokenExpiresAt');
  if (!token || !expiresAt) return false;
  return Date.now() < parseInt(expiresAt);
}

export async function refreshToken() {
  const refreshTok = sessionStorage.getItem('refreshToken');
  if (!refreshTok) throw new Error('No refresh token');

  const response = await fetch(COGNITO_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    },
    body: JSON.stringify({
      AuthFlow: 'REFRESH_TOKEN_AUTH',
      ClientId: COGNITO_CLIENT_ID,
      AuthParameters: {
        REFRESH_TOKEN: refreshTok,
      },
    }),
  });

  const data = await response.json();

  if (data.__type) {
    logout();
    throw new Error('Sesión expirada');
  }

  const result = data.AuthenticationResult;
  const expiresAt = Date.now() + result.ExpiresIn * 1000;

  sessionStorage.setItem('accessToken', result.AccessToken);
  sessionStorage.setItem('idToken', result.IdToken);
  sessionStorage.setItem('tokenExpiresAt', expiresAt.toString());

  scheduleTokenRefresh(result.ExpiresIn);

  return result;
}

let refreshTimeout = null;

function scheduleTokenRefresh(expiresInSeconds) {
  if (refreshTimeout) clearTimeout(refreshTimeout);
  // Refresh 5 minutes before expiry
  const refreshIn = (expiresInSeconds - 300) * 1000;
  if (refreshIn > 0) {
    refreshTimeout = setTimeout(async () => {
      try {
        await refreshToken();
      } catch (e) {
        console.error('Token refresh failed:', e);
      }
    }, refreshIn);
  }
}

// Initialize refresh schedule on load
export function initAuth() {
  const expiresAt = sessionStorage.getItem('tokenExpiresAt');
  if (expiresAt) {
    const remaining = (parseInt(expiresAt) - Date.now()) / 1000;
    if (remaining > 0) {
      scheduleTokenRefresh(remaining);
    }
  }
}

// --- API Functions ---

async function apiRequest(path, options = {}) {
  const token = getAccessToken();
  if (!token) throw new Error('No autenticado');

  const url = `${API_URL}${path}`;
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers,
    },
  };

  const response = await fetch(url, config);

  if (response.status === 401) {
    try {
      await refreshToken();
      config.headers['Authorization'] = `Bearer ${getAccessToken()}`;
      const retry = await fetch(url, config);
      if (!retry.ok) throw new Error('Error en la solicitud');
      return retry.json();
    } catch {
      logout();
      throw new Error('Sesión expirada');
    }
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.message || `Error ${response.status}`);
  }

  return response.json();
}

// Entries
export function addFoodEntry(imageData) {
  return apiRequest('/entries', {
    method: 'POST',
    body: JSON.stringify({ image_data: imageData }),
  });
}

export function deleteEntry(entryId, date) {
  return apiRequest('/entries', {
    method: 'DELETE',
    body: JSON.stringify({ entry_id: entryId, date }),
  });
}

// Summary
export function getDailySummary(date) {
  return apiRequest(`/summary?date=${date}`);
}

export function getWeeklySummary(startDate) {
  return apiRequest(`/summary/week?start=${startDate}`);
}

// Profile
export function getProfile() {
  return apiRequest('/profile');
}

export function createProfile(data) {
  return apiRequest('/profile', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateGoal(dailyCalorieGoal) {
  return apiRequest('/profile/goal', {
    method: 'PUT',
    body: JSON.stringify({ daily_calorie_goal: dailyCalorieGoal }),
  });
}

// Weight
export function addWeight(weightKg) {
  return apiRequest('/weight', {
    method: 'POST',
    body: JSON.stringify({ weight_kg: weightKg }),
  });
}

export function getWeightHistory(limit = 30) {
  return apiRequest(`/weight/history?limit=${limit}`);
}
