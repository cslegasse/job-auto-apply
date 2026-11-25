(() => {
  const f = document.querySelector('form') || document.querySelector('[class*="application-form"]') || document.body;
  return f.innerText.replace(/\n\s*\n+/g, '\n').slice(0, 5000);
})()
