/* CarHub front-end — progressive enhancement only: every feature also works without JS. */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const csrfToken = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';

  async function post(url, data = {}) {
    const body = new URLSearchParams(data);
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
      body,
      credentials: 'same-origin',
    });
    let json = {};
    try { json = await resp.json(); } catch (_) { /* non-JSON error page */ }
    if (!resp.ok) {
      const err = new Error(json.error || 'Something went wrong. Please try again.');
      if (json.auth_required) err.loginUrl = json.login_url;
      throw err;
    }
    return json;
  }

  /* ---------- Toasts ---------- */
  const toastRoot = $('#toasts');
  function toast(message, { error = false, action } = {}) {
    if (!toastRoot) return;
    const el = document.createElement('div');
    el.className = 'toast' + (error ? ' error' : '');
    el.innerHTML = `<svg class="icon" width="18" height="18"><use href="#i-${error ? 'alert' : 'check-circle'}"></use></svg><span></span>`;
    el.querySelector('span').textContent = message;
    if (action) {
      const a = document.createElement('a');
      a.href = action.href;
      a.textContent = action.label;
      el.appendChild(a);
    }
    toastRoot.appendChild(el);
    hideLater(el);
  }
  function hideLater(el, ms = 4200) {
    setTimeout(() => {
      el.classList.add('is-leaving');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    }, ms);
  }
  $$('[data-autohide]').forEach((el) => hideLater(el, 5000));

  function setCount(selector, value) {
    $$(selector).forEach((el) => {
      el.dataset.count = value;
      el.textContent = value > 0 ? value : '';
    });
  }

  /* ---------- Save (wishlist) buttons ---------- */
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-save]');
    if (!btn) return;
    e.preventDefault();
    btn.disabled = true;
    try {
      const res = await post(btn.dataset.save);
      $$(`[data-save="${btn.dataset.save}"]`).forEach((b) => {
        b.classList.toggle('is-saved', res.saved);
        b.setAttribute('aria-pressed', res.saved ? 'true' : 'false');
        const label = b.querySelector('[data-save-label]');
        if (label) label.textContent = res.saved ? 'Saved' : 'Save';
      });
      setCount('[data-saved-count]', res.count);
      toast(res.saved ? 'Saved to your list' : 'Removed from saved cars', res.saved ? { action: { href: '/cars/saved/', label: 'View' } } : {});
    } catch (err) {
      toast(err.message, { error: true });
    } finally {
      btn.disabled = false;
    }
  });

  /* ---------- Add to cart (progressive) ---------- */
  $$('form[data-cart-form]').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      const submitter = e.submitter;
      if (submitter && submitter.name === 'buy_now') return; // full navigation to checkout
      e.preventDefault();
      const btn = submitter || form.querySelector('button');
      btn.disabled = true;
      try {
        const res = await post(form.action);
        setCount('[data-cart-count]', res.cart_count);
        toast(res.message, { action: { href: window.CARHUB.cartUrl, label: 'View cart' } });
        $$('[data-in-cart-label]').forEach((el) => { el.textContent = 'In your cart'; });
      } catch (err) {
        if (err.loginUrl) { window.location = err.loginUrl; return; }
        toast(err.message, { error: true });
      } finally {
        btn.disabled = false;
      }
    });
  });

  /* ---------- Dropdowns: close on outside click / Escape ---------- */
  document.addEventListener('click', (e) => {
    $$('details.dropdown[open]').forEach((d) => { if (!d.contains(e.target)) d.removeAttribute('open'); });
  });

  /* ---------- Drawers (mobile nav, filters) ---------- */
  function openDrawer(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('is-open');
    el.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    const focusable = el.querySelector('input, button, a');
    if (focusable) focusable.focus();
  }
  function closeDrawers() {
    $$('.drawer.is-open, .filters.is-open').forEach((el) => {
      el.classList.remove('is-open');
      el.setAttribute('aria-hidden', 'true');
    });
    document.body.style.overflow = '';
  }
  document.addEventListener('click', (e) => {
    const opener = e.target.closest('[data-drawer-open]');
    if (opener) { e.preventDefault(); openDrawer(opener.dataset.drawerOpen); return; }
    if (e.target.closest('[data-drawer-close]')) { e.preventDefault(); closeDrawers(); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDrawers();
      $$('details.dropdown[open]').forEach((d) => d.removeAttribute('open'));
    }
  });

  /* ---------- Search autocomplete ---------- */
  $$('[data-suggest]').forEach((wrap) => {
    const input = $('input[name="q"]', wrap);
    const list = $('.suggest-list', wrap);
    if (!input || !list) return;
    let timer; let active = -1; let items = [];
    const close = () => { list.classList.remove('is-open'); active = -1; };
    const render = (results) => {
      list.replaceChildren();
      items = results.map((r) => {
        const a = document.createElement('a');
        a.href = r.url;
        a.setAttribute('role', 'option');
        const label = document.createElement('span');
        label.textContent = r.label;
        const count = document.createElement('span');
        count.className = 'count';
        count.textContent = `${r.count} car${r.count === 1 ? '' : 's'}`;
        a.append(label, count);
        list.appendChild(a);
        return a;
      });
      list.classList.toggle('is-open', items.length > 0);
    };
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(async () => {
        try {
          const resp = await fetch(`${window.CARHUB.suggestUrl}?q=${encodeURIComponent(q)}`);
          render((await resp.json()).results || []);
        } catch (_) { close(); }
      }, 160);
    });
    input.addEventListener('keydown', (e) => {
      if (!list.classList.contains('is-open')) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        active = (active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items.forEach((it, i) => it.classList.toggle('is-active', i === active));
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault();
        window.location = items[active].href;
      }
    });
    document.addEventListener('click', (e) => { if (!wrap.contains(e.target)) close(); });
  });

  /* ---------- Hero search tabs ---------- */
  $$('[data-search-panel]').forEach((form) => {
    const hidden = $('input[name="condition"]', form);
    $$('[data-condition]', form).forEach((tab) => tab.addEventListener('click', () => {
      $$('[data-condition]', form).forEach((t) => t.classList.toggle('is-active', t === tab));
      hidden.value = tab.dataset.condition;
    }));
    form.addEventListener('submit', () => {
      $$('input, select', form).forEach((f) => { if (!f.value) f.disabled = true; }); // keep URLs clean
    });
  });

  /* ---------- Browse filters: auto-apply on desktop ---------- */
  const filterForm = $('#filter-form');
  if (filterForm) {
    const autoSubmit = () => window.matchMedia('(min-width: 981px)').matches;
    filterForm.addEventListener('change', (e) => {
      if (e.target.matches('input[type=number]') || !autoSubmit()) return;
      filterForm.requestSubmit();
    });
    filterForm.addEventListener('submit', () => {
      $$('input, select', filterForm).forEach((f) => {
        if ((f.type === 'radio' || f.type === 'checkbox') ? !f.checked : !f.value) f.disabled = true;
      });
    });
    const sortSelect = $('#sort-select');
    if (sortSelect) sortSelect.addEventListener('change', () => sortSelect.form.requestSubmit());
  }

  /* ---------- Gallery + lightbox ---------- */
  const gallery = $('[data-gallery]');
  if (gallery) {
    const main = $('[data-gallery-main] img', gallery);
    const thumbs = $$('[data-thumb]', gallery);
    const counter = $('[data-gallery-counter]', gallery);
    const credit = $('[data-gallery-credit]');
    const lightbox = $('#lightbox');
    const lbImg = lightbox && $('img', lightbox);
    const lbCaption = lightbox && $('.lb-caption', lightbox);
    let index = 0;
    const show = (i) => {
      if (!thumbs.length) return;
      index = (i + thumbs.length) % thumbs.length;
      const t = thumbs[index];
      main.src = t.dataset.src;
      thumbs.forEach((b, n) => b.classList.toggle('is-active', n === index));
      if (counter) counter.textContent = `${index + 1} / ${thumbs.length}`;
      if (credit) {
        credit.replaceChildren();
        if (t.dataset.author) {
          credit.append(`Photo: ${t.dataset.author} · `);
          const a = document.createElement('a');
          a.href = t.dataset.source; a.target = '_blank'; a.rel = 'noopener';
          a.textContent = t.dataset.license || 'source';
          credit.append(a, ' via Wikimedia Commons');
        }
      }
      if (lbImg) { lbImg.src = t.dataset.src; lbCaption.textContent = `${index + 1} / ${thumbs.length}`; }
    };
    thumbs.forEach((t, i) => t.addEventListener('click', () => show(i)));
    $$('[data-gallery-prev]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); show(index - 1); }));
    $$('[data-gallery-next]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); show(index + 1); }));
    if (lightbox) {
      $('[data-gallery-main]', gallery).addEventListener('click', () => { show(index); lightbox.classList.add('is-open'); });
      lightbox.addEventListener('click', (e) => { if (e.target === lightbox || e.target.closest('.lb-close')) lightbox.classList.remove('is-open'); });
      document.addEventListener('keydown', (e) => {
        if (!lightbox.classList.contains('is-open')) return;
        if (e.key === 'Escape') lightbox.classList.remove('is-open');
        if (e.key === 'ArrowLeft') show(index - 1);
        if (e.key === 'ArrowRight') show(index + 1);
      });
    }
    // swipe on touch devices
    let startX = null;
    gallery.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
    gallery.addEventListener('touchend', (e) => {
      if (startX === null) return;
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 40) show(index + (dx < 0 ? 1 : -1));
      startX = null;
    });
  }

  /* ---------- Finance estimate ---------- */
  const calc = $('[data-calc]');
  if (calc) {
    const price = Number(calc.dataset.price);
    const down = $('[name=down]', calc); const months = $('[name=months]', calc); const rate = $('[name=rate]', calc);
    const fmt = (n) => '₦' + Math.round(n).toLocaleString('en-NG');
    const update = () => {
      const d = price * Number(down.value) / 100;
      const principal = price - d;
      const r = Number(rate.value) / 100 / 12; const n = Number(months.value);
      const monthly = r ? principal * r / (1 - Math.pow(1 + r, -n)) : principal / n;
      $('[data-out=down]', calc).textContent = `${down.value}% · ${fmt(d)}`;
      $('[data-out=months]', calc).textContent = `${n} months`;
      $('[data-out=rate]', calc).textContent = `${rate.value}% p.a.`;
      $('[data-out=monthly]', calc).textContent = fmt(monthly);
    };
    [down, months, rate].forEach((el) => el.addEventListener('input', update));
    update();
  }

  /* ---------- Quick message templates ---------- */
  document.addEventListener('click', (e) => {
    const quick = e.target.closest('[data-quick]');
    if (!quick) return;
    const box = quick.form && quick.form.querySelector('textarea');
    if (box) { box.value = quick.dataset.quick; box.focus(); }
  });

  /* ---------- Share ---------- */
  $$('[data-share]').forEach((btn) => btn.addEventListener('click', async () => {
    const data = { title: document.title, url: window.location.href };
    try {
      if (navigator.share) await navigator.share(data);
      else { await navigator.clipboard.writeText(data.url); toast('Link copied to clipboard'); }
    } catch (_) { /* user cancelled */ }
  }));
  $$('select[data-autosubmit]').forEach((sel) => sel.addEventListener('change', () => sel.form.submit()));

  /* ---------- Listing form: photo previews ---------- */
  $$('[data-dropzone]').forEach((zone) => {
    const input = $('input[type=file]', zone);
    const grid = $('[data-previews]');
    const render = () => {
      grid.replaceChildren();
      Array.from(input.files).slice(0, 10).forEach((file, i) => {
        const fig = document.createElement('figure');
        const img = document.createElement('img');
        img.src = URL.createObjectURL(file);
        img.alt = file.name;
        fig.appendChild(img);
        if (i === 0) {
          const cap = document.createElement('figcaption');
          cap.innerHTML = '<span class="badge badge-brand">Cover</span>';
          fig.appendChild(cap);
        }
        grid.appendChild(fig);
      });
    };
    input.addEventListener('change', render);
    ['dragenter', 'dragover'].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add('is-over'); }));
    ['dragleave', 'drop'].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove('is-over'); }));
    zone.addEventListener('drop', (e) => { input.files = e.dataTransfer.files; render(); });
  });

  /* ---------- Chat (WebSocket with polling fallback) ---------- */
  const chat = $('[data-chat]');
  if (chat) {
    const thread = $('[data-thread]', chat);
    const form = $('[data-chat-form]', chat);
    const textarea = $('textarea', form);
    const typingEl = $('[data-typing]', chat);
    let lastId = Number(chat.dataset.lastId || 0);
    let socket = null;
    let pollTimer = null;
    let typingTimer = null;

    const scrollDown = () => { thread.scrollTop = thread.scrollHeight; };
    const append = (m) => {
      if (m.id && m.id <= lastId && thread.querySelector(`[data-id="${m.id}"]`)) return;
      const b = document.createElement('div');
      b.className = 'bubble' + (m.mine ? ' mine' : '');
      b.dataset.id = m.id;
      b.textContent = m.content; // never innerHTML: messages are user input
      const t = document.createElement('time');
      t.textContent = m.time;
      b.appendChild(t);
      thread.appendChild(b);
      lastId = Math.max(lastId, m.id || 0);
      scrollDown();
    };
    scrollDown();

    const poll = async () => {
      try {
        const resp = await fetch(`${chat.dataset.pollUrl}?after=${lastId}`, { credentials: 'same-origin' });
        (await resp.json()).messages.forEach(append);
      } catch (_) { /* offline — try again next tick */ }
    };
    const startPolling = () => { if (!pollTimer) pollTimer = setInterval(poll, 4000); };

    if (!chat.dataset.ws) startPolling(); // no ASGI server: poll over HTTP
    else try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      socket = new WebSocket(`${proto}://${window.location.host}/ws/chat/${chat.dataset.convo}/`);
      socket.addEventListener('message', (e) => {
        const data = JSON.parse(e.data);
        if (data.kind === 'message') append(data.message);
        if (data.kind === 'typing' && typingEl) typingEl.textContent = data.typing ? 'Typing…' : '';
      });
      socket.addEventListener('close', () => { socket = null; startPolling(); });
      socket.addEventListener('error', () => { socket = null; startPolling(); });
    } catch (_) { startPolling(); }

    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 140) + 'px';
      if (socket && socket.readyState === 1) {
        socket.send(JSON.stringify({ type: 'typing', typing: true }));
        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => socket && socket.send(JSON.stringify({ type: 'typing', typing: false })), 1500);
      }
    });
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const content = textarea.value.trim();
      if (!content) return;
      textarea.value = '';
      textarea.style.height = '';
      if (socket && socket.readyState === 1) {
        socket.send(JSON.stringify({ message: content }));
        return;
      }
      try {
        const res = await post(form.action, { content });
        append(res.message);
      } catch (err) {
        textarea.value = content;
        toast(err.message, { error: true });
      }
    });
  }


  /* ---------- Theme toggle (light / dark), remembered per device ---------- */
  $$('[data-theme-toggle]').forEach((btn) => btn.addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('carhub-theme', next); } catch (_) { /* private mode */ }
  }));

  /* ---------- Fade images in once loaded (shimmer placeholder until then) ---------- */
  const markLoaded = (img) => img.classList.add('is-loaded');
  $$('.car-media img, .gallery-main img, .line-item .thumb img').forEach((img) => {
    if (img.complete && img.naturalWidth) markLoaded(img);
    else {
      img.addEventListener('load', () => markLoaded(img), { once: true });
      img.addEventListener('error', () => markLoaded(img), { once: true });
    }
  });

  /* ---------- Header shadow on scroll ---------- */
  const header = $('.site-header');
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ---------- Reveal sections as they scroll into view ---------- */
  const revealables = $$('[data-reveal]');
  if ('IntersectionObserver' in window && revealables.length) {
    const io = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); io.unobserve(entry.target); }
    }), { rootMargin: '0px 0px -8% 0px' });
    revealables.forEach((el) => io.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add('is-visible'));
  }

  /* ---------- Count-up numbers ---------- */
  $$('[data-count-to]').forEach((el) => {
    const target = Number(el.dataset.countTo);
    if (!target || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / 900);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  /* ---------- Moderation: reason chips + approve/reject without reloading ---------- */
  document.addEventListener('click', (e) => {
    const chip = e.target.closest('[data-reason]');
    if (!chip) return;
    const form = chip.closest('form');
    const input = form.querySelector('[name=reason]');
    input.value = chip.dataset.reason;
    $$('[data-reason]', form).forEach((c) => c.classList.toggle('is-picked', c === chip));
    if (input.type !== 'hidden') input.focus();
  });
  // Shared by listings, reviews, photos and verifications in the staff console.
  $$('form[data-moderate]').forEach((form) => form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const decision = e.submitter && e.submitter.value;
    const reason = form.querySelector('[name=reason]');
    const needsReason = (decision === 'reject' && !('reasonOptional' in form.dataset)) || decision === 'correction';
    if (needsReason && !reason.value.trim()) {
      if (reason.type !== 'hidden') reason.focus();
      toast('Add a short reason so they know what to fix.', { error: true });
      return;
    }
    const card = form.closest('[data-mod-item], .mod-card');
    $$('button', form).forEach((b) => { b.disabled = true; });
    try {
      await post(form.action, { decision, reason: reason ? reason.value : '' });
      card.classList.add('is-done', decision === 'approve' ? 'done-ok' : 'done-no');
      setTimeout(() => card.remove(), 320);
      const bump = (key, by) => {
        const el = $(`[data-mod-count="${key}"]`);
        if (el) el.textContent = Math.max(0, Number(el.textContent) + by);
      };
      bump(decision === 'approve' ? 'approved' : 'rejected', 1);
      bump('pending', -1);
      const labels = { approve: 'Approved', reject: 'Rejected', correction: 'Changes requested' };
      toast(`${labels[decision] || 'Done'}. They've been notified.`);
    } catch (err) {
      $$('button', form).forEach((b) => { b.disabled = false; });
      toast(err.message, { error: true });
    }
  }));

  /* ---------- One-time code boxes: one real input drawn as six cells ---------- */
  $$('[data-otp]').forEach((wrap) => {
    const input = $('.otp-input', wrap);
    const cells = $$('.otp-cells span:not(.gap)', wrap);
    const form = wrap.closest('form');
    const paint = () => {
      const v = input.value;
      cells.forEach((cell, i) => {
        cell.textContent = v[i] || '';
        cell.classList.toggle('is-filled', Boolean(v[i]));
        cell.classList.toggle('is-active', document.activeElement === input && (i === v.length || (v.length === cells.length && i === cells.length - 1)));
      });
    };
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g, '').slice(0, cells.length);
      wrap.classList.remove('has-error');
      paint();
      if (input.value.length === cells.length && form && !form.dataset.autoSubmitted) {
        form.dataset.autoSubmitted = '1';
        setTimeout(() => form.requestSubmit(), 120);
      }
    });
    ['focus', 'blur', 'keyup', 'click'].forEach((ev) => input.addEventListener(ev, paint));
    paint();
  });

  /* ---------- "Resend code" cooldown ---------- */
  $$('[data-resend-wait]').forEach((btn) => {
    let left = Number(btn.dataset.resendWait);
    const label = btn.textContent;
    const tick = () => {
      if (left <= 0) { btn.disabled = false; btn.textContent = label; return; }
      btn.disabled = true;
      btn.textContent = `${label} in 0:${String(left).padStart(2, '0')}`;
      left -= 1;
      setTimeout(tick, 1000);
    };
    tick();
  });

  /* ---------- Toggle a hidden panel ---------- */
  $$('[data-toggle-target]').forEach((btn) => btn.addEventListener('click', () => {
    const el = $(btn.dataset.toggleTarget);
    if (!el) return;
    el.hidden = !el.hidden;
    if (!el.hidden) { const f = $('input:not([type=hidden])', el); if (f) f.focus(); }
  }));

  /* ---------- Password fields: show/hide + strength meter ---------- */
  $$('.auth-card input[type=password]').forEach((input) => {
    const wrap = document.createElement('div');
    wrap.className = 'pw-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw-toggle';
    btn.setAttribute('aria-label', 'Show password');
    btn.innerHTML = '<svg class="icon" width="18" height="18"><use href="#i-eye"></use></svg>';
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.classList.toggle('is-on', show);
    });
    wrap.appendChild(btn);
  });
  $$('input[name=password1]').forEach((input) => {
    const field = input.closest('.field');
    let meter = field && $('.strength', field);
    if (!meter && field) {
      meter = document.createElement('div');
      meter.className = 'strength';
      meter.innerHTML = '<i></i><i></i><i></i><i></i>';
      input.closest('.pw-wrap').after(meter);
    }
    if (!meter) return;
    const words = ['Too short', 'Weak', 'Okay', 'Good', 'Strong'];
    const label = $('[data-strength-label]', field);
    input.addEventListener('input', () => {
      const v = input.value;
      let score = 0;
      if (v.length >= 8) score += 1;
      if (v.length >= 12) score += 1;
      if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score += 1;
      if (/\d/.test(v) && /[^A-Za-z0-9]/.test(v)) score += 1;
      if (v.length < 8) score = Math.min(score, 0);
      meter.dataset.score = v ? score : '';
      if (label) label.textContent = v ? `${words[score]} password` : 'At least 8 characters. Mix letters, numbers and symbols.';
    });
  });

  /* ---------- Show progress on submit and block double submits ---------- */
  $$('form[data-busy]').forEach((form) => form.addEventListener('submit', (e) => {
    if (e.defaultPrevented) return;
    const btn = e.submitter || $('button[type=submit], button:not([type])', form);
    if (form.dataset.busy === 'on') { e.preventDefault(); return; }
    form.dataset.busy = 'on';
    if (btn) { btn.classList.add('is-loading'); btn.setAttribute('aria-busy', 'true'); }
  }));
  window.addEventListener('pageshow', () => $$('form[data-busy]').forEach((f) => {
    f.dataset.busy = '';
    delete f.dataset.autoSubmitted;
    $$('.is-loading', f).forEach((b) => b.classList.remove('is-loading'));
  }));

  /* ---------- Hero: featured-car spotlight + rotating headline word ---------- */
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  $$('[data-spotlight]').forEach((stage) => {
    const slides = $$('.stage-slide', stage);
    const thumbs = $$('.stage-thumbs button', stage);
    if (slides.length < 2) return;
    let index = 0;
    let timer = null;
    const DURATION = 5500;
    const show = (i) => {
      index = (i + slides.length) % slides.length;
      slides.forEach((s, n) => {
        const on = n === index;
        s.classList.toggle('is-active', on);
        s.toggleAttribute('aria-hidden', !on);
        s.tabIndex = on ? 0 : -1;
      });
      thumbs.forEach((t, n) => { t.classList.toggle('is-active', n === index); t.setAttribute('aria-selected', n === index); });
      stage.classList.remove('is-ticking');
      void stage.offsetWidth;  // restart the progress bar animation
      if (timer) stage.classList.add('is-ticking');
    };
    const start = () => {
      if (calm || timer) return;
      timer = setInterval(() => show(index + 1), DURATION);
      stage.style.setProperty('--tick', `${DURATION}ms`);
      stage.classList.add('is-ticking');
    };
    const stop = () => { clearInterval(timer); timer = null; stage.classList.remove('is-ticking'); };
    thumbs.forEach((t) => t.addEventListener('click', () => { stop(); show(Number(t.dataset.slide)); start(); }));
    stage.addEventListener('mouseenter', stop);
    stage.addEventListener('mouseleave', start);
    stage.addEventListener('focusin', stop);
    let touchX = null;
    stage.addEventListener('touchstart', (e) => { touchX = e.touches[0].clientX; }, { passive: true });
    stage.addEventListener('touchend', (e) => {
      if (touchX === null) return;
      const dx = e.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 40) { stop(); show(index + (dx < 0 ? 1 : -1)); start(); }
      touchX = null;
    });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => (entry.isIntersecting ? start() : stop())).observe(stage);
    } else start();
    document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  });

  $$('[data-rotate]').forEach((el) => {
    const words = el.dataset.rotate.split(',');
    const span = $('span', el);
    if (calm || !span) return;
    let i = 0;
    setInterval(() => {
      span.classList.add('is-out');
      setTimeout(() => {
        i = (i + 1) % words.length;
        span.textContent = words[i];
        span.classList.remove('is-out');
      }, 320);
    }, 2600);
  });

  /* ---------- Confirm dangerous actions ---------- */
  document.addEventListener('submit', (e) => {
    const msg = e.target.dataset.confirm;
    if (msg && !window.confirm(msg)) e.preventDefault();
  });
})();
