(function () {
  const defaults = {
    pricingSource: 'brain',
    contentSource: 'brain',
    authProvidersEnabled: ['google', 'microsoft', 'apple', 'github'],
    paymentMethodsEnabled: ['google_pay', 'paypal', 'apple_pay', 'card'],
  };

  const existingConfig = window.ASERRAS_UI_CONFIG || {};
  const existingState = window.ASERRAS_UI_STATE || {};

  window.ASERRAS_UI_CONFIG = { ...defaults, ...existingConfig };
  window.ASERRAS_UI_STATE = {
    isAuthenticated: false,
    ...existingState,
  };
})();
