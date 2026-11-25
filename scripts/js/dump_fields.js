(() => {
  const clip = (s, n) => (s || '').trim().replace(/\s+/g, ' ').slice(0, n);
  const lab = el => clip((el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('aria-label')
    || el.placeholder || el.name || el.id, 50);
  const out = [], invalid = [], empty = [], trunc = [];
  for (const el of document.querySelectorAll('input,textarea,select')) {
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(el.type) || el.disabled) continue;
    const l = lab(el);
    let v;
    if (el.type === 'file') v = el.files && el.files.length ? '[file] ' + el.files[0].name : '';
    else if (el.type === 'checkbox' || el.type === 'radio') { if (!el.checked) continue; v = '[x] ' + clip(el.value, 30); }
    else if (el.tagName === 'SELECT') v = clip(el.selectedOptions[0] && el.selectedOptions[0].text, 40);
    else v = clip(el.value, 40);
    if (el.getAttribute('aria-invalid') === 'true') invalid.push(l);
    if (el.required && !v) empty.push(l);
    if (el.maxLength > 0 && el.value.length >= el.maxLength) trunc.push(l + ' (' + el.maxLength + ')');
    if (v) out.push(l + ' = ' + v);
  }
  return out.join('\n') + '\nINVALID: ' + (invalid.join(' | ') || 'none')
    + '\nEMPTY_REQUIRED: ' + (empty.join(' | ') || 'none') + '\nTRUNCATED: ' + (trunc.join(' | ') || 'none');
})()
