/**
 * NutriTrack — Frontend Application
 * Authentication, navigation, and API helper module.
 */
(function () {
  'use strict';

  // ============================================
  // Token Storage (sessionStorage — persists across reloads, clears on tab close)
  // ============================================
  let idToken = sessionStorage.getItem('nt_id') || null;
  let accessToken = sessionStorage.getItem('nt_access') || null;
  let refreshToken = sessionStorage.getItem('nt_refresh') || null;
  let refreshTimerId = null;

  function saveTokens() {
    if (idToken) sessionStorage.setItem('nt_id', idToken);
    if (accessToken) sessionStorage.setItem('nt_access', accessToken);
    if (refreshToken) sessionStorage.setItem('nt_refresh', refreshToken);
  }

  function clearTokens() {
    sessionStorage.removeItem('nt_id');
    sessionStorage.removeItem('nt_access');
    sessionStorage.removeItem('nt_refresh');
  }

  // ============================================
  // Helpers
  // ============================================

  /**
   * Decode a JWT payload (base64url → JSON).
   * Does NOT verify signature — that's the server's job.
   */
  function decodeJwtPayload(token) {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const decoded = atob(payload);
    return JSON.parse(decoded);
  }

  /**
   * Get the expiration timestamp (seconds) from a JWT.
   */
  function getTokenExp(token) {
    const payload = decodeJwtPayload(token);
    return payload ? payload.exp : null;
  }

  // ============================================
  // Cognito Auth
  // ============================================

  function getCognitoEndpoint() {
    const region = window.APP_CONFIG.region || 'us-east-1';
    return 'https://cognito-idp.' + region + '.amazonaws.com/';
  }

  /**
   * Authenticate with Cognito using USER_PASSWORD_AUTH flow.
   */
  async function login(username, password) {
    const endpoint = getCognitoEndpoint();
    const body = {
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: window.APP_CONFIG.cognitoClientId,
      AuthParameters: {
        USERNAME: username,
        PASSWORD: password
      }
    };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorType = errorData.__type || '';
      if (errorType.includes('NotAuthorizedException')) {
        throw new Error('Usuario o contraseña incorrectos.');
      } else if (errorType.includes('UserNotFoundException')) {
        throw new Error('Usuario no encontrado.');
      } else if (errorType.includes('UserNotConfirmedException')) {
        throw new Error('Cuenta no confirmada. Contacta al administrador.');
      } else {
        throw new Error('Error al iniciar sesión. Intenta de nuevo.');
      }
    }

    const data = await response.json();
    const result = data.AuthenticationResult;
    idToken = result.IdToken;
    accessToken = result.AccessToken;
    refreshToken = result.RefreshToken;

    saveTokens();
    scheduleTokenRefresh();
  }

  /**
   * Refresh the access token using the refresh token.
   */
  async function refreshAccessToken() {
    if (!refreshToken) return;

    const endpoint = getCognitoEndpoint();
    const body = {
      AuthFlow: 'REFRESH_TOKEN_AUTH',
      ClientId: window.APP_CONFIG.cognitoClientId,
      AuthParameters: {
        REFRESH_TOKEN: refreshToken
      }
    };

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        // Refresh failed — force re-login
        logout();
        return;
      }

      const data = await response.json();
      const result = data.AuthenticationResult;
      idToken = result.IdToken;
      accessToken = result.AccessToken;
      // Note: RefreshToken is NOT returned on refresh — keep existing one

      saveTokens();
      scheduleTokenRefresh();
    } catch (err) {
      // Network error during refresh — force re-login
      logout();
    }
  }

  /**
   * Schedule a token refresh 5 minutes before the access token expires.
   */
  function scheduleTokenRefresh() {
    if (refreshTimerId) {
      clearTimeout(refreshTimerId);
      refreshTimerId = null;
    }

    if (!accessToken) return;

    const exp = getTokenExp(accessToken);
    if (!exp) return;

    const nowSec = Math.floor(Date.now() / 1000);
    const refreshInSec = exp - nowSec - 300; // 5 minutes before expiry

    if (refreshInSec <= 0) {
      // Token is already expired or about to — refresh immediately
      refreshAccessToken();
      return;
    }

    refreshTimerId = setTimeout(function () {
      refreshAccessToken();
    }, refreshInSec * 1000);
  }

  /**
   * Clear all auth state and return to login screen.
   */
  function logout() {
    idToken = null;
    accessToken = null;
    refreshToken = null;
    clearTokens();

    if (refreshTimerId) {
      clearTimeout(refreshTimerId);
      refreshTimerId = null;
    }

    // Hide nav bar
    var navBar = document.getElementById('nav-bar');
    if (navBar) navBar.classList.remove('visible');

    // Navigate to login screen
    navigateToScreen('login-screen');
  }

  // ============================================
  // API Helper
  // ============================================

  /**
   * Make an authenticated API request.
   * Automatically includes Authorization: Bearer header.
   *
   * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
   * @param {string} path - API path (e.g. '/profile')
   * @param {object|null} body - Request body (will be JSON-stringified)
   * @returns {Promise<any>} Parsed JSON response
   */
  async function apiRequest(method, path, body) {
    const baseUrl = window.APP_CONFIG.apiUrl.replace(/\/$/, '');
    const url = baseUrl + path;

    const headers = {
      'Content-Type': 'application/json'
    };

    if (accessToken) {
      headers['Authorization'] = 'Bearer ' + accessToken;
    }

    const options = {
      method: method,
      headers: headers
    };

    if (body && method !== 'GET') {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Error en la solicitud' }));
      const error = new Error(errorData.message || 'Error en la solicitud');
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  // ============================================
  // Navigation
  // ============================================

  let currentScreen = 'login-screen';

  /**
   * Navigate to a screen with slide animation.
   * @param {string} screenId - The ID of the target screen element
   * @param {string} direction - 'left' or 'right' for animation direction
   */
  function navigateToScreen(screenId, direction) {
    if (screenId === currentScreen) return;

    var screens = document.querySelectorAll('.screen');
    var targetScreen = document.getElementById(screenId);
    if (!targetScreen) return;

    // Determine animation direction
    var animClass = direction === 'right' ? 'animate-slide-right' : 'animate-slide-left';

    // Hide all screens
    screens.forEach(function (s) {
      s.classList.remove('active');
      s.classList.remove('animate-slide-left');
      s.classList.remove('animate-slide-right');
    });

    // Show and animate target screen
    targetScreen.classList.add('active');
    targetScreen.classList.add(animClass);

    // Remove animation class after it completes to allow re-triggering
    targetScreen.addEventListener('animationend', function handler() {
      targetScreen.classList.remove(animClass);
      targetScreen.removeEventListener('animationend', handler);
    });

    // Update active nav item
    var navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(function (item) {
      item.classList.remove('active');
      item.removeAttribute('aria-current');
      if (item.getAttribute('data-screen') === screenId) {
        item.classList.add('active');
        item.setAttribute('aria-current', 'page');
      }
    });

    currentScreen = screenId;
  }

  /**
   * Determine slide direction based on screen order.
   */
  function getNavDirection(fromScreen, toScreen) {
    var order = ['dashboard-screen', 'weekly-screen', 'weight-screen', 'settings-screen'];
    var fromIdx = order.indexOf(fromScreen);
    var toIdx = order.indexOf(toScreen);
    if (fromIdx === -1 || toIdx === -1) return 'left';
    return toIdx > fromIdx ? 'left' : 'right';
  }

  // ============================================
  // Login Form Handler
  // ============================================

  function setupLoginForm() {
    var form = document.getElementById('login-form');
    var errorEl = document.getElementById('login-error');
    var loginBtn = document.getElementById('login-btn');

    if (!form) return;

    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      var username = document.getElementById('login-username').value.trim();
      var password = document.getElementById('login-password').value;

      // Clear previous error
      errorEl.style.display = 'none';
      errorEl.textContent = '';

      if (!username || !password) {
        showLoginError('Ingresa usuario y contraseña.');
        return;
      }

      // Disable button during login
      loginBtn.disabled = true;
      loginBtn.textContent = 'Iniciando sesión...';

      try {
        await login(username, password);
        await onLoginSuccess();
      } catch (err) {
        showLoginError(err.message || 'Error al iniciar sesión. Intenta de nuevo.');
      } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Iniciar sesión';
      }
    });
  }

  function showLoginError(message) {
    var errorEl = document.getElementById('login-error');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.style.display = 'block';
      // Trigger shake animation on the form
      var form = document.getElementById('login-form');
      if (form) {
        form.classList.add('animate-shake');
        form.addEventListener('animationend', function handler() {
          form.classList.remove('animate-shake');
          form.removeEventListener('animationend', handler);
        });
      }
    }
  }

  /**
   * After successful login, check profile and navigate accordingly.
   */
  async function onLoginSuccess() {
    // Show nav bar
    var navBar = document.getElementById('nav-bar');
    if (navBar) navBar.classList.add('visible');

    try {
      // Check if user has a profile
      await apiRequest('GET', '/profile');
      // Profile exists — go to dashboard
      navigateToScreen('dashboard-screen', 'left');
    } catch (err) {
      if (err.status === 404) {
        // No profile — show onboarding
        navigateToScreen('onboarding-screen', 'left');
        // Hide nav bar during onboarding
        var navBar2 = document.getElementById('nav-bar');
        if (navBar2) navBar2.classList.remove('visible');
      } else {
        // Unexpected error — go to dashboard anyway
        navigateToScreen('dashboard-screen', 'left');
      }
    }
  }

  // ============================================
  // Nav Bar Click Handler
  // ============================================

  function setupNavBar() {
    var navItems = document.querySelectorAll('.nav-item[data-screen]');
    navItems.forEach(function (item) {
      item.addEventListener('click', function () {
        var targetScreen = item.getAttribute('data-screen');
        var direction = getNavDirection(currentScreen, targetScreen);
        navigateToScreen(targetScreen, direction);
      });
    });
  }

  // ============================================
  // Logout Handler
  // ============================================

  function setupLogout() {
    var logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        logout();
      });
    }
  }

  // ============================================
  // Initialization
  // ============================================

  function init() {
    setupLoginForm();
    setupNavBar();
    setupLogout();

    // Auto-login if session tokens exist from a previous page load
    if (accessToken) {
      scheduleTokenRefresh();
      onLoginSuccess();
    }
  }

  // Expose necessary functions globally for other modules
  window.NutriTrack = {
    apiRequest: apiRequest,
    navigateToScreen: navigateToScreen,
    logout: logout,
    getAccessToken: function () { return accessToken; }
  };

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
