// Read-only: the application form's visible text (question labels, radio groups), capped.
// Use once per form to enumerate questions instead of a full-page screenshot.
(() => {
  const f = document.querySelector('form') || document.querySelector('[class*="application-form"]') || document.body;
  return f.innerText.replace(/\n\s*\n+/g, '\n').slice(0, 5000);
})()
