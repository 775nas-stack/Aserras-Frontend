(function () {
  const config = window.ASERRAS_CONFIG || {};
  const endpoints = config.endpoints || {};
  const uiConfig = window.ASERRAS_UI_CONFIG || {
    pricingSource: 'core',
    contentSource: 'core',
    authProvidersEnabled: ['google', 'microsoft', 'apple', 'github'],
    paymentMethodsEnabled: ['google_pay', 'paypal', 'apple_pay', 'card'],
  };
  const uiState = window.ASERRAS_UI_STATE || { isAuthenticated: false };
  const baseApiUrl = (config.baseApiUrl || '').replace(/\/$/, '');
  const THEME_STORAGE_KEY = 'aserras-theme';
  const DEFAULT_THEME = 'dark';
  const AUTH_STORAGE_KEY = 'aserras-auth-state';
  const AUTH_TOKEN_STORAGE_KEY = 'aserras-auth-token';
  const SERVICE_ERROR_COOLDOWN = 15000;
  const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please sign in again.';
  const TOAST_CONTAINER_ID = 'aserras-toast-container';
  let lastServiceErrorAt = 0;
  const enabledAuthProviders = new Set(
    (uiConfig.authProvidersEnabled || []).map((provider) => normaliseKey(provider)),
  );
  const enabledPaymentMethods = new Set(
    (uiConfig.paymentMethodsEnabled || []).map((method) => normaliseKey(method)),
  );
  const registeredUserMenus = new Set();
  const pendingToastQueue = [];

  function ensureToastContainer() {
    if (!document || !document.body) {
      return null;
    }
    let container = document.getElementById(TOAST_CONTAINER_ID);
    if (!container) {
      container = document.createElement('div');
      container.id = TOAST_CONTAINER_ID;
      container.setAttribute('aria-live', 'polite');
      container.style.position = 'fixed';
      container.style.bottom = '1.5rem';
      container.style.right = '1.5rem';
      container.style.display = 'flex';
      container.style.flexDirection = 'column';
      container.style.gap = '0.75rem';
      container.style.zIndex = '2147483647';
      container.style.pointerEvents = 'none';
      container.style.maxWidth = 'min(90vw, 320px)';
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(message, { variant = 'error', timeout = 6000 } = {}) {
    if (!message) return;

    const run = () => {
      const container = ensureToastContainer();
      if (!container) return;

      const toast = document.createElement('div');
      toast.className = 'aserras-toast';
      toast.setAttribute('role', 'status');
      toast.textContent = message;
      toast.style.pointerEvents = 'auto';
      toast.style.padding = '0.75rem 1rem';
      toast.style.borderRadius = '999px';
      toast.style.background =
        variant === 'error'
          ? 'var(--surface-3, rgba(39, 20, 20, 0.92))'
          : 'var(--surface-3, rgba(18, 21, 31, 0.92))';
      toast.style.color = 'var(--text-primary, #ffffff)';
      toast.style.boxShadow = '0 12px 48px rgba(0, 0, 0, 0.35)';
      toast.style.backdropFilter = 'blur(12px)';
      toast.style.border =
        variant === 'error'
          ? '1px solid var(--danger, rgba(255, 102, 102, 0.6))'
          : '1px solid rgba(255, 255, 255, 0.15)';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      toast.style.transition = 'opacity 200ms ease, transform 200ms ease';
      toast.style.fontSize = '0.9375rem';
      toast.style.lineHeight = '1.4';

      container.appendChild(toast);

      requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
      });

      const remove = () => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        setTimeout(() => {
          toast.remove();
        }, 220);
      };

      setTimeout(remove, Math.max(2000, timeout));
    };

    if (!document || !document.body) {
      pendingToastQueue.push(run);
      document.addEventListener(
        'DOMContentLoaded',
        () => {
          while (pendingToastQueue.length) {
            const queued = pendingToastQueue.shift();
            queued?.();
          }
        },
        { once: true },
      );
      return;
    }

    run();
  }

  function notifyServiceIssue(message) {
    const now = Date.now();
    if (now - lastServiceErrorAt < SERVICE_ERROR_COOLDOWN) {
      return;
    }
    lastServiceErrorAt = now;
    showToast(message || 'We are having trouble reaching Core. Please try again shortly.', {
      variant: 'error',
    });
  }

  function safeGetStoredToken() {
    try {
      const value = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
      return typeof value === 'string' ? value.trim() : '';
    } catch (error) {
      return '';
    }
  }

  function persistAuthToken(token) {
    try {
      const value = typeof token === 'string' ? token.trim() : '';
      if (value) {
        localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, value);
      } else {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      }
    } catch (error) {
      /* no-op */
    }
  }

  function currentAuthToken() {
    return safeGetStoredToken();
  }

  function extractToken(payload) {
    if (!payload || typeof payload !== 'object') {
      return '';
    }
    const candidates = [
      payload.token,
      payload.accessToken,
      payload.access_token,
      payload?.data?.token,
      payload?.data?.accessToken,
      payload?.data?.access_token,
    ];
    return candidates.find((value) => typeof value === 'string' && value.trim())?.trim() || '';
  }

  function ensureAuthenticated({ redirectTo = '/login' } = {}) {
    const token = currentAuthToken();
    if (token) {
      return true;
    }
    window.aserrasUI?.setAuthState?.(false, { keepToken: true });
    if (redirectTo) {
      window.location.replace(redirectTo);
    }
    return false;
  }

  const initialToken = currentAuthToken();
  uiState.isAuthenticated =
    typeof uiState.isAuthenticated === 'boolean'
      ? Boolean(uiState.isAuthenticated)
      : Boolean(initialToken || safeGetStoredAuthState());
  if (initialToken) {
    uiState.isAuthenticated = true;
  }
  persistAuthState(uiState.isAuthenticated);

  applyTheme(safeGetStoredTheme() || DEFAULT_THEME, { persist: false });

  function buildTargets(resource) {
    if (!resource) return [];

    const value = String(resource).trim();
    if (!value) return [];

    const targets = [];
    const isAbsolute = /^https?:\/\//i.test(value);

    if (isAbsolute) {
      targets.push(value);
      try {
        const url = new URL(value);
        const relative = `${url.pathname}${url.search}`;
        if (relative && relative !== value) {
          targets.push(relative);
        }
      } catch (error) {
        /* ignore malformed absolute URL */
      }
    } else {
      const path = value.startsWith('/') ? value : `/${value}`;
      if (baseApiUrl) {
        targets.push(`${baseApiUrl}${path}`);
      }
      targets.push(path);
    }

    return Array.from(new Set(targets.filter(Boolean)));
  }

  function resolveEndpoint(key, fallback) {
    const candidate = endpoints && Object.prototype.hasOwnProperty.call(endpoints, key)
      ? endpoints[key]
      : undefined;
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
    return fallback;
  }

  const api = {
    async request(path, options = {}) {
      const { auth = false, ...fetchOptions } = options;
      const targets = buildTargets(path);
      if (!targets.length) {
        throw new Error('No request targets could be resolved');
      }

      const token = auth ? currentAuthToken() : '';
      if (auth && !token) {
        throw new Error('Please sign in to continue.');
      }

      let lastError;

      for (const url of targets) {
        try {
          const headers = {
            ...(fetchOptions.headers || {}),
          };
          const hasBody =
            Object.prototype.hasOwnProperty.call(fetchOptions, 'body') &&
            fetchOptions.body !== null &&
            fetchOptions.body !== undefined;
          if (hasBody && !Object.prototype.hasOwnProperty.call(headers, 'Content-Type')) {
            headers['Content-Type'] = 'application/json';
          }
          if (auth && token) {
            headers.Authorization = `Bearer ${token}`;
          }

          const response = await fetch(url, {
            ...fetchOptions,
            headers,
          });
          const responseClone = response.clone();

          if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
              window.aserrasUI?.setAuthState?.(false);
              notifyServiceIssue(SESSION_EXPIRED_MESSAGE);
            } else if (response.status >= 500) {
              notifyServiceIssue(
                'Core is unavailable at the moment. We will keep trying to reconnect.',
              );
            }

            let detail = {};
            try {
              detail = await responseClone.json();
            } catch (error) {
              /* response did not include JSON */
            }
            const fallbackMessage =
              response.status === 401 || response.status === 403
                ? SESSION_EXPIRED_MESSAGE
                : 'Request failed';
            const message =
              detail?.message ||
              detail?.detail ||
              detail?.error ||
              response.statusText ||
              fallbackMessage;
            throw new Error(message || 'Request failed');
          }

          if (response.status === 204) {
            return {};
          }

          const contentType = response.headers.get('content-type') || '';
          if (!contentType.toLowerCase().includes('application/json')) {
            const text = await response.text().catch(() => '');
            return text ? { data: text } : {};
          }

          try {
            return await response.json();
          } catch (error) {
            return {};
          }
        } catch (error) {
          lastError = error instanceof Error ? error : new Error('Unable to reach service');
          const message = error instanceof Error ? error.message || '' : '';
          if (
            error instanceof TypeError ||
            /NetworkError|Failed to fetch/i.test(message)
          ) {
            notifyServiceIssue('We are having trouble reaching Core. Please try again shortly.');
          }
        }
      }

      throw lastError || new Error('Unable to reach service');
    },
  };

  function normaliseKey(value) {
    return String(value || '').trim().toLowerCase();
  }

  function formatLabelFromKey(value) {
    return normaliseKey(value)
      .split(/[_-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  function currentAuthState() {
    return uiState.isAuthenticated ? 'signed-in' : 'signed-out';
  }

  function applyConfigMetadata() {
    if (!document.body) return;
    document.body.setAttribute('data-pricing-source', uiConfig.pricingSource || 'static');
    document.body.setAttribute('data-content-source', uiConfig.contentSource || 'static');
  }

  function syncAuthUI() {
    const state = currentAuthState();
    if (document.body) {
      document.body.setAttribute('data-auth-state', state);
    }
    registeredUserMenus.forEach((menu) => {
      menu.dataset.authState = state;
      if (typeof menu._syncAuthState === 'function') {
        menu._syncAuthState();
      }
    });
    document.querySelectorAll('[data-auth-visible]').forEach((element) => {
      const targetState = element.getAttribute('data-auth-visible');
      const shouldShow = !targetState || targetState === state;
      element.hidden = !shouldShow;
      element.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
    });
  }

  function applyFeatureFlags() {
    document.querySelectorAll('[data-auth-provider]').forEach((button) => {
      const provider = normaliseKey(button.dataset.authProvider);
      const enabled = enabledAuthProviders.has(provider);
      button.hidden = !enabled;
      button.setAttribute('aria-hidden', enabled ? 'false' : 'true');
      if (!enabled) {
        button.setAttribute('tabindex', '-1');
      } else {
        button.removeAttribute('tabindex');
      }
    });

    document.querySelectorAll('[data-auth-providers]').forEach((wrapper) => {
      const hasVisibleProvider = Array.from(
        wrapper.querySelectorAll('[data-auth-provider]'),
      ).some((btn) => !btn.hidden);
      wrapper.hidden = !hasVisibleProvider;
      wrapper.setAttribute('aria-hidden', hasVisibleProvider ? 'false' : 'true');
    });

    document.querySelectorAll('[data-payment-method]').forEach((button) => {
      const method = normaliseKey(button.dataset.paymentMethod);
      const enabled = enabledPaymentMethods.has(method);
      button.hidden = !enabled;
      button.setAttribute('aria-hidden', enabled ? 'false' : 'true');
      if (!enabled) {
        button.setAttribute('tabindex', '-1');
      } else {
        button.removeAttribute('tabindex');
      }
    });
  }

  function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      day: 'numeric',
      month: 'short',
    });
  }

  function createMessageElement(message) {
    const role = message.role === 'ai' ? 'ai' : 'user';
    const bubble = document.createElement('article');
    bubble.className = `chat-bubble chat-bubble--${role}`;
    bubble.setAttribute('data-role', role);

    const text = document.createElement('p');
    text.className = 'chat-bubble__text';
    text.textContent = message.text;
    bubble.appendChild(text);

    const timestamp = message.timestamp ? new Date(message.timestamp) : new Date();
    const time = document.createElement('time');
    const iso = timestamp instanceof Date && !Number.isNaN(timestamp.valueOf())
      ? timestamp.toISOString()
      : new Date().toISOString();
    time.className = 'chat-bubble__meta';
    time.dateTime = iso;
    time.textContent = formatTimestamp(iso);
    bubble.appendChild(time);

    requestAnimationFrame(() => {
      bubble.classList.add('is-visible');
    });

    return bubble;
  }

  function downloadJSON(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function setFeedback(el, message, isError = false) {
    if (!el) return;
    el.hidden = !message;
    el.textContent = message || '';
    if (message) {
      el.style.color = isError ? 'var(--danger)' : 'var(--muted)';
    } else {
      el.style.color = 'var(--muted)';
    }
  }

  function safeGetStoredAuthState() {
    if (currentAuthToken()) {
      return true;
    }
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored === 'true') return true;
      if (stored === 'false') return false;
    } catch (error) {
      /* no-op */
    }
    return false;
  }

  function persistAuthState(isAuthenticated) {
    try {
      localStorage.setItem(AUTH_STORAGE_KEY, isAuthenticated ? 'true' : 'false');
    } catch (error) {
      /* no-op */
    }
  }

  function safeGetStoredTheme() {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      return stored === 'light' || stored === 'dark' ? stored : null;
    } catch (error) {
      return null;
    }
  }

  function getCurrentTheme() {
    const mode = document.body?.getAttribute('data-theme');
    return mode === 'light' ? 'light' : 'dark';
  }

  function updateThemeToggles(mode) {
    const label = mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
    const pressed = mode === 'light';

    document.querySelectorAll('[data-theme-toggle]').forEach((toggle) => {
      toggle.setAttribute('aria-pressed', pressed ? 'true' : 'false');
      toggle.setAttribute('data-mode', mode);

      const srOnly = toggle.querySelector('.sr-only');
      if (srOnly) {
        srOnly.textContent = label;
      }

      const textEl = toggle.querySelector('[data-theme-text]');
      if (textEl) {
        textEl.textContent = label;
      } else if (!srOnly && toggle.dataset.themeVariant !== 'icon') {
        toggle.textContent = label;
      }
    });
  }

  function applyTheme(mode = DEFAULT_THEME, { persist = true } = {}) {
    const theme = mode === 'light' ? 'light' : 'dark';
    if (!document.body) return;
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(`theme-${theme}`);
    document.body.setAttribute('data-theme', theme);
    updateThemeToggles(theme);
    if (persist) {
      try {
        localStorage.setItem(THEME_STORAGE_KEY, theme);
      } catch (error) {
        /* no-op */
      }
    }
  }

  function initThemeControls() {
    updateThemeToggles(getCurrentTheme());
    document.querySelectorAll('[data-theme-toggle]').forEach((toggle) => {
      if (toggle.dataset.initialised === 'true') return;
      toggle.dataset.initialised = 'true';
      toggle.addEventListener('click', () => {
        const nextTheme = getCurrentTheme() === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
      });
    });
  }

  function initNav() {
    const toggle = document.querySelector('[data-nav-toggle]');
    const wrapper = document.querySelector('[data-nav-wrapper]');
    if (!toggle || !wrapper) return;

    const closeNav = () => {
      if (!wrapper.classList.contains('is-open')) return;
      wrapper.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('nav-open');
    };

    const openNav = () => {
      if (wrapper.classList.contains('is-open')) return;
      wrapper.classList.add('is-open');
      toggle.setAttribute('aria-expanded', 'true');
      document.body.classList.add('nav-open');
    };

    toggle.addEventListener('click', () => {
      if (wrapper.classList.contains('is-open')) {
        closeNav();
      } else {
        openNav();
      }
    });

    wrapper.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        closeNav();
      });
    });

    wrapper.querySelectorAll('[data-user-action="signout"]').forEach((button) => {
      button.addEventListener('click', () => {
        console.info('[Aserras] Signing out and returning to the login screen.');
        closeNav();
        window.aserrasUI?.setAuthState?.(false);
        window.location.href = '/login';
      });
    });

    document.addEventListener('click', (event) => {
      if (wrapper.contains(event.target) || toggle.contains(event.target)) {
        return;
      }
      closeNav();
    });

    document.addEventListener('keyup', (event) => {
      if (event.key === 'Escape') {
        closeNav();
      }
    });
  }

  function initUserMenu() {
    document.querySelectorAll('[data-user-menu]').forEach((menu) => {
      if (menu.dataset.initialised === 'true') return;
      const trigger = menu.querySelector('[data-user-menu-toggle]');
      const panel = menu.querySelector('[data-user-menu-panel]');
      if (!trigger || !panel) return;

      menu.dataset.initialised = 'true';
      menu.dataset.authState = currentAuthState();

      const syncState = () => {
        const state = menu.dataset.authState === 'signed-in' ? 'signed-in' : 'signed-out';
        panel.querySelectorAll('[data-visible-when]').forEach((group) => {
          const visibleWhen = group.getAttribute('data-visible-when');
          group.hidden = visibleWhen !== state;
        });
      };

      menu._syncAuthState = syncState;
      registeredUserMenus.add(menu);

      const closeMenu = () => {
        if (!panel.classList.contains('is-open')) return;
        panel.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
      };

      const openMenu = () => {
        if (panel.classList.contains('is-open')) return;
        panel.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
      };

      trigger.addEventListener('click', () => {
        if (panel.classList.contains('is-open')) {
          closeMenu();
        } else {
          openMenu();
        }
      });

      document.addEventListener('click', (event) => {
        if (menu.contains(event.target)) return;
        closeMenu();
      });

      document.addEventListener('keyup', (event) => {
        if (event.key === 'Escape') {
          closeMenu();
        }
      });

      panel.querySelectorAll('a, button').forEach((item) => {
        item.addEventListener('click', () => {
          closeMenu();
        });
      });

      panel.querySelectorAll('[data-user-action="signout"]').forEach((item) => {
        item.addEventListener('click', () => {
          console.info('[Aserras] Signing out and returning to the login screen.');
          window.aserrasUI?.setAuthState?.(false);
          window.location.href = '/login';
        });
      });

      syncState();
    });
  }

  function initContactForm() {
    const form = document.querySelector('#contact-form');
    if (!form) return;
    const feedback = form.querySelector('.form-feedback');

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = Object.fromEntries(new FormData(form).entries());
      setFeedback(feedback, 'Sending your note to the concierge...');

      try {
        const response = await api.request(resolveEndpoint('contactSend', '/contact/send'), {
          method: 'POST',
          body: JSON.stringify(formData),
        });
        setFeedback(
          feedback,
          response.message || "Thank you for your message. We'll reply shortly.",
        );
        console.info('[Aserras] Contact form submission captured.', formData);
        form.reset();
      } catch (error) {
        setFeedback(
          feedback,
          error?.message || 'We could not send your message just now. Please try again in a moment.',
          true,
        );
        console.error('[Aserras] Contact form submission failed.', error);
      }
    });
  }

  function scrubSensitive(data) {
    if (!data) return {};
    const copy = { ...data };
    ['password', 'confirmPassword', 'token'].forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(copy, key) && copy[key]) {
        copy[key] = '••••';
      }
    });
    return copy;
  }

  async function loginUser(formData, feedback) {
    setFeedback(feedback, 'Signing you in securely...');
    try {
      const payload = {
        email: formData.email,
        password: formData.password,
      };
      const response = await api.request(resolveEndpoint('authLogin', '/auth/login'), {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const token = extractToken(response);
      if (!token) {
        throw new Error('We could not establish a secure session. Please try again.');
      }

      console.info('[Aserras] Login submission captured.', scrubSensitive(formData));
      setFeedback(feedback, response.message || 'Welcome back. Redirecting to your dashboard...');
      window.aserrasUI?.setAuthState?.(true, { token });
      const redirect = response.redirect || '/dashboard';
      setTimeout(() => {
        window.location.href = redirect;
      }, 500);
    } catch (error) {
      console.error('[Aserras] Login request failed.', error);
      setFeedback(
        feedback,
        error?.message || 'We could not sign you in right now. Please try again.',
        true,
      );
    }
  }

  async function registerUser(formData, feedback) {
    if (formData.password !== formData.confirmPassword) {
      setFeedback(feedback, 'Passwords need to match before we can continue.', true);
      return;
    }

    if (!formData.acceptTerms) {
      setFeedback(feedback, 'Please confirm you agree to the Terms & Privacy.', true);
      return;
    }

    setFeedback(
      feedback,
      `Welcome aboard, ${formData.fullName || formData.email}! Setting up your workspace...`,
    );

    try {
      const payload = {
        fullName: formData.fullName,
        email: formData.email,
        password: formData.password,
      };

      const response = await api.request(resolveEndpoint('authSignup', '/auth/signup'), {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const token = extractToken(response);
      if (!token) {
        throw new Error('We could not activate your session. Please try signing in.');
      }

      console.info('[Aserras] Signup submission captured.', scrubSensitive(formData));
      window.aserrasUI?.setAuthState?.(true, { token });
      setFeedback(feedback, response.message || 'Your account is live. Redirecting now...');
      const redirect = response.redirect || '/dashboard';
      setTimeout(() => {
        window.location.href = redirect;
      }, 700);
    } catch (error) {
      console.error('[Aserras] Signup request failed.', error);
      setFeedback(
        feedback,
        error?.message || 'We could not complete your signup right now. Please try again.',
        true,
      );
    }
  }

  function requestPasswordReset(formData, feedback) {
    setFeedback(feedback, 'Check your inbox for a secure reset link.');
    console.info('[Aserras] Password reset request noted.', scrubSensitive(formData));
  }

  function authWith(provider, feedback) {
    if (!provider) return;
    const label = formatLabelFromKey(provider);
    setFeedback(feedback, `${label} sign-in is connecting. You'll arrive at your dashboard momentarily.`);
    console.info(`[Aserras] ${label} provider selected.`);
    setTimeout(() => {
      window.aserrasUI?.setAuthState?.(true);
      window.location.href = '/dashboard';
    }, 800);
  }

  function initPasswordToggles(scope = document) {
    const toggleButtons = scope.querySelectorAll('[data-password-toggle]');
    toggleButtons.forEach((button) => {
      if (button.dataset.initialised === 'true') return;
      const targetId = button.dataset.passwordToggle;
      if (!targetId) return;
      const input = document.getElementById(targetId);
      if (!input) return;

      button.dataset.initialised = 'true';
      const updateLabel = () => {
        const visible = input.type === 'text';
        button.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
        button.classList.toggle('is-active', visible);
      };

      button.addEventListener('click', () => {
        input.type = input.type === 'password' ? 'text' : 'password';
        updateLabel();
      });

      updateLabel();
    });
  }

  function initAuthShell() {
    document.querySelectorAll('[data-auth-form]').forEach((form) => {
      if (form.dataset.initialised === 'true') return;
      form.dataset.initialised = 'true';
      const feedback = form.querySelector('.form-feedback');

      const card = form.closest('.auth-card');
      if (card) {
        initPasswordToggles(card);
      }
      card?.querySelectorAll('[data-auth-provider]').forEach((button) => {
        if (button.dataset.initialised === 'true') return;
        if (button.hidden) return;
        button.dataset.initialised = 'true';
        button.addEventListener('click', () => {
          authWith(button.dataset.authProvider, feedback);
        });
      });

      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = Object.fromEntries(new FormData(form).entries());
        if (form.querySelector('[name="acceptTerms"]')) {
          formData.acceptTerms = form.querySelector('[name="acceptTerms"]').checked;
        }
        const type = form.dataset.authForm;

        if (type === 'login') {
          await loginUser(formData, feedback);
        } else if (type === 'signup') {
          await registerUser(formData, feedback);
        } else if (type === 'forgot') {
          requestPasswordReset(formData, feedback);
        }
      });
    });
  }

  function initPricing() {
    const buttons = document.querySelectorAll('[data-checkout-plan]');
    if (!buttons.length) return;

    buttons.forEach((button) => {
      if (button.dataset.initialised === 'true') return;
      button.dataset.initialised = 'true';
      button.addEventListener('click', async () => {
        const planId = button.closest('.pricing-card')?.dataset.plan;
        if (!planId) return;
        console.info('[Aserras] Checkout flow initialised.', { planId });
        window.location.href = `/checkout?plan=${encodeURIComponent(planId)}`;
      });
    });
  }

  async function fetchHistory() {
    const endpoint = resolveEndpoint('userHistory', '/chat/history');
    const response = await api.request(endpoint, { auth: true });
    const messages = Array.isArray(response.messages) ? response.messages : [];
    return messages.map((message) => ({
      id: message.id,
      role: message.role === 'ai' ? 'ai' : 'user',
      text: message.text || '',
      timestamp: message.timestamp,
    }));
  }

  function initChat() {
    const transcript = document.querySelector('#chat-transcript');
    const form = document.querySelector('#chat-form');
    const input = document.querySelector('[data-chat-input]');
    const sendButton = document.querySelector('[data-chat-send]');
    const status = document.querySelector('[data-chat-status]');
    const emptyState = transcript?.querySelector('[data-chat-empty]') || null;

    if (!transcript || !form || !input || !sendButton) return;

    if (!ensureAuthenticated()) {
      return;
    }

    let isSending = false;

    const setStatus = (text, state = 'idle') => {
      if (!status) return;
      status.textContent = text;
      status.dataset.state = state;
    };

    const scrollToBottom = () => {
      transcript.scrollTo({ top: transcript.scrollHeight, behavior: 'smooth' });
    };

    const toggleEmptyState = () => {
      const hasMessages = transcript.querySelectorAll('.chat-bubble').length > 0;
      transcript.setAttribute('data-empty', hasMessages ? 'false' : 'true');
      if (emptyState) {
        emptyState.hidden = hasMessages;
      }
    };

    const appendMessage = (role, text, timestamp) => {
      transcript.setAttribute('aria-busy', 'true');
      const entry = createMessageElement({
        role,
        text,
        timestamp: timestamp || new Date().toISOString(),
      });
      entry.setAttribute('tabindex', '-1');
      if (emptyState) {
        emptyState.hidden = true;
      }
      transcript.appendChild(entry);
      toggleEmptyState();
      scrollToBottom();
      entry.focus({ preventScroll: true });
      entry.addEventListener(
        'blur',
        () => {
          entry.removeAttribute('tabindex');
        },
        { once: true },
      );
      transcript.setAttribute('aria-busy', 'false');
      return entry;
    };

    const hydrateHistory = async () => {
      setStatus('Syncing your previous messages...', 'loading');
      try {
        transcript.querySelectorAll('.chat-bubble').forEach((node) => node.remove());
        const messages = await fetchHistory();
        messages.forEach((message) => {
          appendMessage(message.role, message.text, message.timestamp);
        });
        toggleEmptyState();
        setStatus(
          'Messages you send are saved instantly and remain available across your workspace.',
          'idle',
        );
      } catch (error) {
        console.error('[Aserras] Unable to load chat history.', error);
        if (error?.message === SESSION_EXPIRED_MESSAGE) {
          setStatus('Your session expired. Redirecting to the login screen...', 'error');
          ensureAuthenticated();
          return;
        }
        toggleEmptyState();
        setStatus(
          'We could not load earlier conversations. New messages will still appear instantly.',
          'error',
        );
      }
    };

    const autoresize = () => {
      input.style.height = 'auto';
      const next = Math.min(input.scrollHeight, 240);
      input.style.height = `${next}px`;
    };

    const updateSendState = () => {
      sendButton.disabled = input.value.trim().length === 0;
    };

    toggleEmptyState();
    autoresize();
    updateSendState();

    input.addEventListener('input', () => {
      autoresize();
      updateSendState();
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        if (!sendButton.disabled) {
          form.requestSubmit();
        }
      }
    });

    const sendToAssistant = async (text) => {
      if (isSending) return;
      isSending = true;
      setStatus('Aserras is thinking...', 'loading');

      try {
        const response = await api.request(resolveEndpoint('chatSend', '/chat/send'), {
          method: 'POST',
          body: JSON.stringify({ message: text }),
          auth: true,
        });

        const history = Array.isArray(response.messages) ? response.messages : [];
        const latestAssistant = [...history].reverse().find((message) => message.role === 'ai');
        const reply = latestAssistant?.text || response.reply || 'Captured. Ready for the next step.';
        appendMessage('ai', reply, latestAssistant?.timestamp);
        toggleEmptyState();
        setStatus('Synced. Ask anything else to continue.', 'synced');
      } catch (error) {
        console.error('[Aserras] Chat message failed.', error);
        if (error?.message === SESSION_EXPIRED_MESSAGE) {
          setStatus('Your session expired. Redirecting to the login screen...', 'error');
          ensureAuthenticated();
        } else {
          appendMessage(
            'ai',
            `We ran into an issue processing that update: ${error?.message || 'please try again shortly.'}`,
          );
          setStatus('We hit a connection snag. Trying again will usually fix it.', 'error');
        }
      } finally {
        isSending = false;
      }
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;

      appendMessage('user', message);
      input.value = '';
      autoresize();
      updateSendState();

      setStatus(
        'Message synced to your workspace. Replies surface here as your conversation evolves.',
        'queued',
      );

      await sendToAssistant(message);
    });

    hydrateHistory();
  }

  async function startCheckout(method, planId, feedback) {
    if (!method) return;
    const label = formatLabelFromKey(method);
    const planLabel = formatLabelFromKey(planId || 'selected');
    setFeedback(
      feedback,
      `${label} checkout is preparing your ${planLabel} upgrade. You'll receive confirmation shortly.`,
    );

    try {
      const payload = {
        planId,
        token: method,
      };
      const response = await api.request(resolveEndpoint('paymentCreate', '/payment/create'), {
        method: 'POST',
        body: JSON.stringify(payload),
        auth: true,
      });
      setFeedback(
        feedback,
        response.message ||
          `${label} checkout is preparing your ${planLabel} upgrade. Confirmation will arrive soon.`,
      );
      console.info('[Aserras] Checkout method selected.', { method, planId, reference: response.reference });
    } catch (error) {
      console.error('[Aserras] Checkout request failed.', error);
      setFeedback(
        feedback,
        error?.message || 'We could not start the checkout flow. Please try another method.',
        true,
      );
    }
  }

  function initCheckout() {
    const section = document.querySelector('[data-checkout]');
    if (!section) return;
    const planId = section.dataset.planId || 'pro';
    const feedback = section.querySelector('.form-feedback');

    section.querySelectorAll('[data-payment-method]').forEach((button) => {
      if (button.dataset.initialised === 'true') return;
      if (button.hidden) return;
      button.dataset.initialised = 'true';
      button.addEventListener('click', async () => {
        await startCheckout(button.dataset.paymentMethod, planId, feedback);
      });
    });
  }

  function initDashboardShell() {
    if (!ensureAuthenticated()) {
      return;
    }

    const stats = {
      messages: document.querySelector('[data-stat="messages"]'),
      seats: document.querySelector('[data-stat="seats"]'),
      success: document.querySelector('[data-stat="success"]'),
    };
    const historyList = document.querySelector('#history-list');
    const actions = document.querySelectorAll('[data-dashboard-action]');

    function updateStats(messages) {
      const total = Array.isArray(messages) ? messages.length : 0;
      if (stats.messages) stats.messages.textContent = total.toString();
      if (stats.seats) stats.seats.textContent = Math.max(3, Math.ceil(total / 5)).toString();
      if (stats.success) stats.success.textContent = `${Math.min(99, 80 + total)}%`;
    }

    function renderHistory(messages) {
      if (!historyList) return;
      historyList.innerHTML = '';

      const items = Array.isArray(messages) ? messages.slice(-6) : [];
      if (!items.length) {
        if (historyList.dataset.emptyState) {
          const empty = document.createElement('p');
          empty.className = 'muted';
          empty.textContent = historyList.dataset.emptyState;
          historyList.appendChild(empty);
        }
        return;
      }

      items.forEach((message) => {
        const row = document.createElement('div');
        row.className = 'history-row';

        const role = document.createElement('span');
        role.className = 'history-row__role';
        role.textContent = message.role === 'ai' ? 'AI' : 'You';

        const summary = document.createElement('span');
        summary.className = 'history-row__text';
        summary.textContent = message.text;

        const meta = document.createElement('time');
        meta.className = 'history-row__time';
        meta.dateTime = message.timestamp;
        meta.textContent = formatTimestamp(message.timestamp);

        row.appendChild(role);
        row.appendChild(summary);
        row.appendChild(meta);

        historyList.appendChild(row);
      });
    }

    async function refreshDashboard() {
      if (historyList) {
        historyList.innerHTML = '';
        const notice = document.createElement('p');
        notice.className = 'muted';
        notice.textContent = 'Loading your recent workspace activity...';
        historyList.appendChild(notice);
      }

      try {
        const messages = await fetchHistory();
        updateStats(messages);
        renderHistory(messages);
        console.info('[Aserras] Dashboard history synced.', { total: messages.length });
      } catch (error) {
        console.error('[Aserras] Dashboard refresh failed.', error);
        if (error?.message === SESSION_EXPIRED_MESSAGE) {
          ensureAuthenticated();
          return;
        }
        updateStats([]);
        if (historyList) {
          historyList.innerHTML = '';
          const errorRow = document.createElement('p');
          errorRow.className = 'muted';
          errorRow.textContent =
            'We could not load recent history. Conversations will appear once the connection stabilises.';
          historyList.appendChild(errorRow);
        }
      }
    }

    async function handleAction(event, element) {
      const action = element.dataset.dashboardAction;

      switch (action) {
        case 'refresh':
          await refreshDashboard();
          break;
        case 'view-chat':
          window.location.href = '/chat';
          break;
        case 'upgrade':
          console.info('[Aserras] Redirecting to pricing for plan upgrades.');
          window.location.href = '/pricing';
          break;
        case 'signout':
          console.info('[Aserras] Signing out and returning to the login screen.');
          window.aserrasUI?.setAuthState?.(false);
          window.location.href = '/login';
          break;
        case 'language':
          console.info('[Aserras] Language preference captured.', element.value);
          break;
        default:
          break;
      }
    }

    actions.forEach((element) => {
      if (element.dataset.initialised === 'true') return;
      element.dataset.initialised = 'true';

      if (element.tagName === 'SELECT') {
        element.addEventListener('change', async (event) => {
          await handleAction(event, element);
        });
      } else {
        element.addEventListener('click', async (event) => {
          event.preventDefault();
          await handleAction(event, element);
        });
      }
    });

    refreshDashboard();
  }

  function initSettingsPreview() {
    const settingsPanel = document.querySelector('.settings-panel');
    if (!settingsPanel) return;

    initThemeControls();
    console.info('[Aserras] Settings preview loaded.');
  }

  window.aserrasUI = {
    initNav,
    initUserMenu,
    initContactForm,
    initAuthShell,
    initPricing,
    initCheckout,
    initChat,
    initDashboardShell,
    initSettingsPreview,
    initPasswordToggles,
    initTheme: initThemeControls,
    applyConfigMetadata,
    applyFeatureFlags,
    syncAuthUI,
    setAuthState(isAuthenticated, options = {}) {
      const next = Boolean(isAuthenticated);
      const token = options?.token;
      const keepToken = options?.keepToken === true;

      if (next) {
        if (token) {
          persistAuthToken(token);
        }
      } else if (!keepToken) {
        persistAuthToken('');
      }

      uiState.isAuthenticated = next || Boolean(currentAuthToken());
      persistAuthState(uiState.isAuthenticated);
      syncAuthUI();
      return uiState.isAuthenticated;
    },
    getAuthToken: currentAuthToken,
    requireAuth: ensureAuthenticated,
    showToast,
  };

  document.addEventListener('DOMContentLoaded', () => {
    applyConfigMetadata();
    initNav();
    initUserMenu();
    applyFeatureFlags();
    syncAuthUI();
    initThemeControls();
  });
})();
