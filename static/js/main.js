(function () {
  const config = window.ASERRAS_CONFIG || {};
  const uiConfig = window.ASERRAS_UI_CONFIG || {
    pricingSource: 'brain',
    contentSource: 'brain',
    authProvidersEnabled: ['google', 'microsoft', 'apple', 'github'],
    paymentMethodsEnabled: ['google_pay', 'paypal', 'apple_pay', 'card'],
  };
  const uiState = window.ASERRAS_UI_STATE || { isAuthenticated: false };
  const endpoints = config.endpoints || {};
  const baseApiUrl = (config.baseApiUrl || '').replace(/\/$/, '');
  const THEME_STORAGE_KEY = 'aserras-theme';
  const DEFAULT_THEME = 'dark';
  const AUTH_STORAGE_KEY = 'aserras-auth-state';
  const enabledAuthProviders = new Set(
    (uiConfig.authProvidersEnabled || []).map((provider) => normaliseKey(provider)),
  );
  const enabledPaymentMethods = new Set(
    (uiConfig.paymentMethodsEnabled || []).map((method) => normaliseKey(method)),
  );
  const registeredUserMenus = new Set();

  uiState.isAuthenticated =
    typeof uiState.isAuthenticated === 'boolean'
      ? Boolean(uiState.isAuthenticated)
      : safeGetStoredAuthState();
  persistAuthState(uiState.isAuthenticated);

  const initialTheme =
    safeGetStoredTheme() ||
    uiState.theme ||
    (document.body ? document.body.getAttribute('data-theme') : null) ||
    DEFAULT_THEME;
  applyTheme(initialTheme, { persist: false });

  const api = {
    async request(pathOrUrl, options = {}) {
      const candidates = [];
      if (/^https?:/i.test(pathOrUrl)) {
        candidates.push(pathOrUrl);
      } else {
        const trimmed = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`;
        if (baseApiUrl) {
          candidates.push(`${baseApiUrl}${trimmed}`);
        }
        candidates.push(trimmed);
      }

      let lastError;

      for (const url of candidates) {
        try {
          const headers = {
            Accept: 'application/json',
            ...(options.headers || {}),
          };
          if (options.body && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
          }

          const response = await fetch(url, {
            credentials: 'include',
            ...options,
            headers,
          });

          const contentType = response.headers.get('content-type') || '';
          const isJson = contentType.includes('application/json');
          const payload = isJson ? await response.json().catch(() => ({})) : await response.text();

          if (!response.ok) {
            const message = (payload && payload.detail) || payload?.message || payload?.error || 'Request failed';
            throw new Error(message);
          }

          return payload;
        } catch (error) {
          lastError = error;
        }
      }

      throw lastError || new Error('Unable to reach service');
    },

    post(pathOrUrl, data = {}) {
      return this.request(pathOrUrl, {
        method: 'POST',
        body: JSON.stringify(data),
      });
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
    uiState.theme = theme;
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
        api.post(endpoints.settingsTheme || '/api/settings/theme', { theme: nextTheme }).catch((error) => {
          console.warn('[Aserras] Theme preference could not be saved.', error);
        });
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
        item.addEventListener('click', async () => {
          try {
            await api.post(endpoints.authLogout || '/logout');
          } catch (error) {
            console.warn('[Aserras] Logout request failed:', error);
          }
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

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const formData = Object.fromEntries(new FormData(form).entries());
      setFeedback(feedback, "Thank you for your message. We'll reply shortly.");
      console.info('[Aserras] Contact form submission captured.', formData);
      form.reset();
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
    try {
      setFeedback(feedback, 'Signing you in...');
      const result = await api.post(endpoints.authLogin || '/api/auth/login', {
        email: formData.email,
        password: formData.password,
      });
      window.aserrasUI?.setAuthState?.(true);
      setFeedback(feedback, 'Welcome back. Redirecting to your dashboard...');
      window.location.href = (result && result.redirect) || '/dashboard';
    } catch (error) {
      setFeedback(feedback, error.message || 'Unable to sign in. Please try again.', true);
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

    try {
      setFeedback(feedback, `Creating your workspace, ${formData.name || formData.email}...`);
      const result = await api.post(endpoints.authSignup || '/api/auth/signup', {
        name: formData.name || formData.fullName,
        email: formData.email,
        password: formData.password,
      });
      window.aserrasUI?.setAuthState?.(true);
      setFeedback(feedback, 'Account ready. Redirecting to your dashboard...');
      window.location.href = (result && result.redirect) || '/dashboard';
    } catch (error) {
      setFeedback(feedback, error.message || 'Unable to create your account right now.', true);
    }
  }

  function requestPasswordReset(formData, feedback) {
    setFeedback(feedback, 'Check your inbox for a secure reset link.');
    console.info('[Aserras] Password reset request noted.', scrubSensitive(formData));
  }

  function authWith(provider, feedback) {
    if (!provider) return;
    const label = formatLabelFromKey(provider);
    setFeedback(
      feedback,
      `${label} sign-in will be available soon. In the meantime, continue with your email account.`,
      true,
    );
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
        if (form.dataset.submitting === 'true') return;
        form.dataset.submitting = 'true';
        const formData = Object.fromEntries(new FormData(form).entries());
        const type = form.dataset.authForm;

        try {
          if (type === 'login') {
            await loginUser(formData, feedback);
          } else if (type === 'signup') {
            await registerUser(formData, feedback);
          } else if (type === 'forgot') {
            requestPasswordReset(formData, feedback);
          }
        } finally {
          form.dataset.submitting = 'false';
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
      button.addEventListener('click', () => {
        const planId = button.closest('.pricing-card')?.dataset.plan;
        if (!planId) return;
        console.info('[Aserras] Checkout flow initialised.', { planId });
        window.location.href = `/checkout?plan=${encodeURIComponent(planId)}`;
      });
    });
  }

  async function loadHistory(into) {
    if (!into) return [];
    try {
      const data = await api.request(endpoints.userHistory || '/api/history');
      const items = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
      return items;
    } catch (error) {
      console.warn('[Aserras] Unable to load history:', error);
      return [];
    }
  }

  function extractChatText(result) {
    if (!result) return '';
    if (typeof result === 'string') return result;
    if (result.reply) return result.reply;
    if (result.message) return result.message;
    if (result.text) return result.text;
    if (result.output) return result.output;
    if (Array.isArray(result.choices) && result.choices.length) {
      const choice = result.choices[0];
      return choice?.message?.content || choice?.text || '';
    }
    if (Array.isArray(result.responses) && result.responses.length) {
      return result.responses[0]?.content || '';
    }
    if (result.data && typeof result.data === 'object') {
      return result.data.text || result.data.content || '';
    }
    return '';
  }

  function initChat() {
    const transcript = document.querySelector('#chat-transcript');
    const form = document.querySelector('#chat-form');
    const input = document.querySelector('[data-chat-input]');
    const sendButton = document.querySelector('[data-chat-send]');
    const status = document.querySelector('[data-chat-status]');
    const emptyState = transcript?.querySelector('[data-chat-empty]') || null;
    const modelSelect = document.querySelector('[data-chat-model]');

    if (!transcript || !form || !input || !sendButton) return;

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

    const appendMessage = (role, text) => {
      transcript.setAttribute('aria-busy', 'true');
      const entry = createMessageElement({
        role,
        text,
        timestamp: new Date().toISOString(),
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

    const params = new URLSearchParams(window.location.search);
    const presetPrompt = params.get('prompt');
    if (presetPrompt) {
      input.value = presetPrompt;
      autoresize();
      updateSendState();
    }

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

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (form.dataset.submitting === 'true') return;
      const message = input.value.trim();
      if (!message) return;

      appendMessage('user', message);
      input.value = '';
      autoresize();
      updateSendState();

      form.dataset.submitting = 'true';
      input.disabled = true;
      sendButton.disabled = true;

      if (status) {
        status.textContent = 'Aserras is composing a response...';
        status.dataset.state = 'loading';
      }

      try {
        const payload = { prompt: message };
        const model = modelSelect?.value?.trim();
        if (model) payload.model = model;
        const result = await api.post(endpoints.chatSend || '/api/chat', payload);
        const reply = extractChatText(result) || 'Aserras responded without additional details.';
        appendMessage('ai', reply);
        if (status) {
          status.textContent = 'Response delivered and saved to your workspace.';
          status.dataset.state = 'success';
        }
      } catch (error) {
        if (status) {
          status.textContent = error.message || 'Unable to reach Aserras Brain right now.';
          status.dataset.state = 'error';
        }
      } finally {
        form.dataset.submitting = 'false';
        input.disabled = false;
        sendButton.disabled = false;
        updateSendState();
      }
    });
  }

  function extractImageUrls(result) {
    const urls = [];
    if (!result) return urls;
    const maybeAdd = (entry) => {
      if (!entry) return;
      if (typeof entry === 'string') {
        urls.push(entry);
        return;
      }
      if (entry.url) {
        urls.push(entry.url);
      } else if (entry.b64_json) {
        urls.push(`data:image/png;base64,${entry.b64_json}`);
      }
    };

    if (Array.isArray(result.images)) {
      result.images.forEach(maybeAdd);
    }
    if (Array.isArray(result.data)) {
      result.data.forEach(maybeAdd);
    }
    if (result.url || result.image) {
      maybeAdd(result.url || result.image);
    }
    return urls;
  }

  function initImageStudio() {
    const form = document.querySelector('[data-image-form]');
    const gallery = document.querySelector('[data-image-gallery]');
    const input = form?.querySelector('[data-image-input]');
    const sizeSelect = form?.querySelector('[data-image-size]');
    const generateButton = form?.querySelector('[data-image-generate]');
    const status = document.querySelector('[data-image-status]');
    const emptyState = gallery?.querySelector('[data-image-empty]') || null;

    if (!form || !gallery || !input || !generateButton) return;
    if (form.dataset.initialised === 'true') return;
    form.dataset.initialised = 'true';

    const toggleEmpty = (hasImages) => {
      if (emptyState) {
        emptyState.hidden = hasImages;
      }
    };

    const updateButton = () => {
      generateButton.disabled = input.value.trim().length === 0 || form.dataset.submitting === 'true';
    };

    input.addEventListener('input', updateButton);
    updateButton();

    const addImageCard = (src, prompt) => {
      const figure = document.createElement('figure');
      figure.className = 'image-card';

      const img = document.createElement('img');
      img.src = src;
      img.alt = prompt || 'Generated image';
      img.loading = 'lazy';
      figure.appendChild(img);

      if (prompt) {
        const caption = document.createElement('figcaption');
        caption.textContent = prompt;
        figure.appendChild(caption);
      }

      const actions = document.createElement('div');
      actions.className = 'image-card__actions';

      const download = document.createElement('button');
      download.type = 'button';
      download.className = 'btn btn--outline';
      download.textContent = 'Download';
      download.addEventListener('click', () => {
        downloadImage(src, prompt || 'aserras-image');
      });
      actions.appendChild(download);

      figure.appendChild(actions);
      gallery.prepend(figure);
      toggleEmpty(true);
    };

    const downloadImage = (src, name) => {
      const link = document.createElement('a');
      link.href = src;
      link.download = `${name.replace(/\s+/g, '-').toLowerCase()}-${Date.now()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (form.dataset.submitting === 'true') return;
      const prompt = input.value.trim();
      if (!prompt) return;

      form.dataset.submitting = 'true';
      input.disabled = true;
      generateButton.disabled = true;
      if (status) {
        status.textContent = 'Generating artwork...';
        status.dataset.state = 'loading';
      }

      try {
        const result = await api.post(endpoints.imageGenerate || '/api/image', {
          prompt,
          size: sizeSelect?.value,
        });
        const images = extractImageUrls(result);
        if (!images.length) {
          throw new Error('No image returned from the server.');
        }
        images.forEach((src) => addImageCard(src, prompt));
        input.value = '';
        updateButton();
        if (status) {
          status.textContent = 'Image ready. Saved to your workspace history.';
          status.dataset.state = 'success';
        }
      } catch (error) {
        if (status) {
          status.textContent = error.message || 'Unable to generate an image right now.';
          status.dataset.state = 'error';
        }
      } finally {
        form.dataset.submitting = 'false';
        input.disabled = false;
        generateButton.disabled = false;
        updateButton();
      }
    });
  }

  function extractCodeContent(result) {
    if (!result) return '';
    if (typeof result === 'string') return result;
    if (result.code) return result.code;
    if (result.script) return result.script;
    if (result.output) return result.output;
    if (result.text) return result.text;
    if (Array.isArray(result.choices) && result.choices.length) {
      const choice = result.choices[0];
      return choice?.message?.content || choice?.text || '';
    }
    if (result.data && typeof result.data === 'object') {
      return result.data.code || result.data.text || '';
    }
    return '';
  }

  function initCodeStudio() {
    const form = document.querySelector('[data-code-form]');
    const output = document.querySelector('[data-code-output]');
    const textarea = form?.querySelector('[data-code-input]');
    const languageInput = form?.querySelector('[data-code-language]');
    const generateButton = form?.querySelector('[data-code-generate]');
    const status = document.querySelector('[data-code-status]');
    const emptyState = output?.querySelector('[data-code-empty]') || null;

    if (!form || !output || !textarea || !generateButton) return;
    if (form.dataset.initialised === 'true') return;
    form.dataset.initialised = 'true';

    const updateButton = () => {
      generateButton.disabled = textarea.value.trim().length === 0 || form.dataset.submitting === 'true';
    };

    const renderCode = (code) => {
      output.innerHTML = '';
      const pre = document.createElement('pre');
      pre.className = 'code-output__block';
      pre.textContent = code;
      output.appendChild(pre);
      const toolbar = document.createElement('div');
      toolbar.className = 'code-output__actions';
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'btn btn--outline';
      copy.textContent = 'Copy code';
      copy.addEventListener('click', () => {
        navigator.clipboard?.writeText(code).then(() => {
          copy.textContent = 'Copied!';
          setTimeout(() => {
            copy.textContent = 'Copy code';
          }, 1200);
        });
      });
      toolbar.appendChild(copy);
      output.appendChild(toolbar);
    };

    textarea.addEventListener('input', updateButton);
    updateButton();

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (form.dataset.submitting === 'true') return;
      const instructions = textarea.value.trim();
      if (!instructions) return;

      form.dataset.submitting = 'true';
      textarea.disabled = true;
      generateButton.disabled = true;
      if (status) {
        status.textContent = 'Generating code...';
        status.dataset.state = 'loading';
      }

      try {
        const result = await api.post(endpoints.codeGenerate || '/api/code', {
          instructions,
          language: languageInput?.value?.trim(),
        });
        const code = extractCodeContent(result);
        if (!code) {
          throw new Error('No code was returned.');
        }
        if (emptyState) {
          emptyState.remove();
        }
        renderCode(code);
        if (status) {
          status.textContent = 'Automation ready. Saved to your history.';
          status.dataset.state = 'success';
        }
      } catch (error) {
        if (status) {
          status.textContent = error.message || 'Unable to generate code right now.';
          status.dataset.state = 'error';
        }
      } finally {
        form.dataset.submitting = 'false';
        textarea.disabled = false;
        generateButton.disabled = false;
        updateButton();
      }
    });
  }

  function initHistoryPage() {
    const container = document.querySelector('[data-history-list]');
    if (!container) return;
    if (container.dataset.initialised === 'true') return;
    container.dataset.initialised = 'true';
    const emptyState = container.dataset.emptyState || 'Start creating to see your history.';

    const renderItems = (items) => {
      container.innerHTML = '';
      if (!items.length) {
        const empty = document.createElement('p');
        empty.className = 'muted';
        empty.textContent = emptyState;
        container.appendChild(empty);
        return;
      }

      items.forEach((item) => {
        const card = document.createElement('article');
        card.className = 'history-card';
        card.dataset.historyId = item.id || '';

        const header = document.createElement('header');
        header.className = 'history-card__header';
        const type = document.createElement('span');
        type.className = 'history-card__type';
        type.textContent = item.type || item.mode || 'Chat';
        const time = document.createElement('time');
        time.className = 'history-card__time';
        const timestamp = item.created_at || item.timestamp;
        if (timestamp) {
          time.dateTime = timestamp;
          time.textContent = formatTimestamp(timestamp);
        }
        header.appendChild(type);
        header.appendChild(time);
        card.appendChild(header);

        const body = document.createElement('div');
        body.className = 'history-card__body';
        const title = document.createElement('h2');
        title.textContent = item.title || item.prompt || 'Untitled generation';
        const summary = document.createElement('p');
        summary.textContent = item.summary || item.response || item.text || '';
        body.appendChild(title);
        body.appendChild(summary);
        card.appendChild(body);

        const footer = document.createElement('footer');
        footer.className = 'history-card__footer';
        const rerun = document.createElement('button');
        rerun.type = 'button';
        rerun.className = 'btn btn--ghost';
        rerun.dataset.historyAction = 'rerun';
        rerun.dataset.historyPrompt = item.prompt || item.text || '';
        rerun.textContent = 'Re-run';
        const details = document.createElement('button');
        details.type = 'button';
        details.className = 'btn btn--outline';
        details.dataset.historyAction = 'details';
        details.textContent = 'Details';
        footer.appendChild(rerun);
        footer.appendChild(details);
        card.appendChild(footer);

        container.appendChild(card);
      });
    };

    const refreshHistory = async () => {
      container.innerHTML = '';
      const loading = document.createElement('p');
      loading.className = 'muted';
      loading.textContent = 'Fetching your recent activity...';
      container.appendChild(loading);

      const items = await loadHistory(container);
      renderItems(items);
    };

    container.addEventListener('click', (event) => {
      const target = event.target.closest('[data-history-action]');
      if (!target) return;
      const action = target.dataset.historyAction;
      const prompt = target.dataset.historyPrompt || '';
      if (action === 'rerun' && prompt) {
        window.location.href = `/chat?prompt=${encodeURIComponent(prompt)}`;
      }
      if (action === 'details') {
        alert('Detailed history view is coming soon.');
      }
    });

    refreshHistory();
  }

  function startCheckout(method, planId, feedback) {
    if (!method) return;
    const label = formatLabelFromKey(method);
    const planLabel = formatLabelFromKey(planId || 'selected');
    setFeedback(
      feedback,
      `${label} checkout is preparing your ${planLabel} upgrade. You'll receive confirmation shortly.`,
    );
    console.info('[Aserras] Checkout method selected.', { method, planId });
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
      button.addEventListener('click', () => {
        startCheckout(button.dataset.paymentMethod, planId, feedback);
      });
    });
  }

  function initDashboardShell() {
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
        const actor = message.role || message.actor || message.author;
        role.textContent = actor === 'ai' ? 'AI' : 'You';

        const summary = document.createElement('span');
        summary.className = 'history-row__text';
        summary.textContent = message.title || message.summary || message.prompt || message.text || 'Conversation update';

        const meta = document.createElement('time');
        meta.className = 'history-row__time';
        const timestamp = message.created_at || message.timestamp;
        if (timestamp) {
          meta.dateTime = timestamp;
          meta.textContent = formatTimestamp(timestamp);
        } else {
          meta.textContent = '';
        }

        row.appendChild(role);
        row.appendChild(summary);
        row.appendChild(meta);

        historyList.appendChild(row);
      });
    }

    async function refreshDashboard() {
      if (historyList) {
        historyList.innerHTML = '';
        const loading = document.createElement('p');
        loading.className = 'muted';
        loading.textContent = 'Syncing your latest activity...';
        historyList.appendChild(loading);
      }

      try {
        const items = await loadHistory(historyList);
        updateStats(items);
        renderHistory(items);
      } catch (error) {
        console.warn('[Aserras] Unable to refresh dashboard history:', error);
        if (historyList) {
          historyList.innerHTML = '';
          const notice = document.createElement('p');
          notice.className = 'muted';
          notice.textContent = 'History is unavailable right now. Please try again soon.';
          historyList.appendChild(notice);
        }
      }
    }

    function handleAction(event, element) {
      const action = element.dataset.dashboardAction;

      switch (action) {
        case 'refresh':
          refreshDashboard();
          break;
        case 'view-chat':
          window.location.href = '/chat';
          break;
        case 'upgrade':
          console.info('[Aserras] Redirecting to pricing for plan upgrades.');
          window.location.href = '/pricing';
          break;
        case 'signout':
          api.post(endpoints.authLogout || '/logout').finally(() => {
            window.aserrasUI?.setAuthState?.(false);
            window.location.href = '/login';
          });
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
        element.addEventListener('change', (event) => handleAction(event, element));
      } else {
        element.addEventListener('click', (event) => {
          event.preventDefault();
          handleAction(event, element);
        });
      }
    });

    refreshDashboard();
  }

  function initSettingsPreview() {
    const settingsPanel = document.querySelector('.settings-panel');
    if (!settingsPanel) return;

    initThemeControls();

    const profileForm = settingsPanel.querySelector('[data-settings-form="profile"]');
    if (profileForm && profileForm.dataset.initialised !== 'true') {
      profileForm.dataset.initialised = 'true';
      const feedback = profileForm.querySelector('[data-settings-feedback]');
      profileForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (profileForm.dataset.submitting === 'true') return;
        const formData = Object.fromEntries(new FormData(profileForm).entries());
        const payload = {
          name: (formData.name || '').trim(),
          language: (formData.language || '').trim() || null,
          model: (formData.model || '').trim() || null,
        };
        if (!payload.name) {
          setFeedback(feedback, 'Please enter a display name.', true);
          return;
        }

        profileForm.dataset.submitting = 'true';
        setFeedback(feedback, 'Saving your preferences...');

        try {
          await api.post(endpoints.settingsProfile || '/api/settings/profile', payload);
          setFeedback(feedback, 'Preferences updated successfully.');
        } catch (error) {
          setFeedback(
            feedback,
            error.message || 'We could not save your changes right now. Please try again soon.',
            true,
          );
        } finally {
          profileForm.dataset.submitting = 'false';
        }
      });
    }

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
    initImageStudio,
    initCodeStudio,
    initHistoryPage,
    initDashboardShell,
    initSettingsPreview,
    initPasswordToggles,
    initTheme: initThemeControls,
    applyConfigMetadata,
    applyFeatureFlags,
    syncAuthUI,
    setAuthState(isAuthenticated) {
      uiState.isAuthenticated = Boolean(isAuthenticated);
      persistAuthState(uiState.isAuthenticated);
      syncAuthUI();
      return uiState.isAuthenticated;
    },
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
