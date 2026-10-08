/* DriverZone: maps, booking, live trip tracking and the driver app.
   Maps: Leaflet + OpenStreetMap data via CARTO tiles. Search: Photon (photon.komoot.io). Routes are planned
   server-side with OSRM, so prices can't be tampered with in the browser. */
(() => {
  'use strict';
  if (!window.L) return;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const money = (v) => '₦' + Math.round(Number(v)).toLocaleString('en-NG');
  const PHOTON = 'https://photon.komoot.io';
  const NG_BBOX = '2.6,4.2,14.7,13.9';

  async function postForm(url, data) {
    const resp = await fetch(url, {
      method: 'POST', credentials: 'same-origin', body: new URLSearchParams(data),
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
    });
    let json = {};
    try { json = await resp.json(); } catch (_) { /* not JSON */ }
    if (!resp.ok) throw new Error(json.error || 'Something went wrong. Please try again.');
    return json;
  }

  /* ---------- Map with theme-aware tiles ---------- */
  function tiles() {
    // Standard OpenStreetMap tiles (free, attribution required). Dark mode is a CSS filter on the tile pane.
    return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
  }
  function makeMap(el, center, zoom) {
    const map = L.map(el, { zoomControl: false, attributionControl: true }).setView(center, zoom);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    tiles().addTo(map);
    return map;
  }
  const carSvg = (cls) => `<svg viewBox="0 0 32 32" width="34" height="34"><g class="car-${cls}"><rect x="9" y="3" width="14" height="26" rx="6"/><rect class="glass" x="11" y="8" width="10" height="6" rx="2"/><rect class="glass" x="11" y="20" width="10" height="4" rx="1.5"/></g></svg>`;
  const carIcon = (heading = 0, cls = 'economy', live = false) => L.divIcon({
    className: 'dz-car-icon', iconSize: [34, 34], iconAnchor: [17, 17],
    html: `<div class="dz-car ${live ? 'is-live' : ''}" style="transform:rotate(${heading}deg)">${carSvg(cls)}</div>`,
  });
  const pin = (kind) => L.divIcon({ className: 'dz-pin-icon', iconSize: [30, 40], iconAnchor: [15, 38],
    html: `<div class="dz-pin ${kind}"><span></span></div>` });
  const routeStyle = { color: '#ffb21e', weight: 6, opacity: .95, lineCap: 'round' };
  const routeShadow = { color: '#0f1419', weight: 10, opacity: .18, lineCap: 'round' };
  const approachStyle = { color: '#64748b', weight: 4, opacity: .8, dashArray: '2 10', lineCap: 'round' };

  /* ---------- Smoothly animate a marker to a new position ---------- */
  function glide(marker, to, ms = 2200) {
    const from = marker.getLatLng();
    const start = performance.now();
    cancelAnimationFrame(marker._dzAnim);
    const step = (now) => {
      const t = Math.min(1, (now - start) / ms);
      marker.setLatLng([from.lat + (to[0] - from.lat) * t, from.lng + (to[1] - from.lng) * t]);
      if (t < 1) marker._dzAnim = requestAnimationFrame(step);
    };
    marker._dzAnim = requestAnimationFrame(step);
  }

  /* ---------- Photon address search ---------- */
  function label(f) {
    const p = f.properties || {};
    const main = p.name || [p.housenumber, p.street].filter(Boolean).join(' ') || p.street || p.district || p.city;
    const area = [p.district !== main && p.district, p.city !== main && p.city, p.state].filter(Boolean);
    return { main: main || 'Dropped pin', area: [...new Set(area)].join(', ') };
  }
  async function reverse(lat, lng) {
    try {
      const r = await fetch(`${PHOTON}/reverse?lat=${lat}&lon=${lng}&lang=en`);
      const j = await r.json();
      if (j.features && j.features.length) { const l = label(j.features[0]); return [l.main, l.area].filter(Boolean).join(', '); }
    } catch (_) { /* offline */ }
    return `Pinned location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
  }
  function autocomplete(field, getBias, onPick) {
    const input = $('input', field);
    const list = $('.dz-suggest', field);
    let timer = null;
    let items = [];
    let active = -1;
    const close = () => { list.classList.remove('is-open'); active = -1; };
    const render = () => {
      list.replaceChildren(...items.map((f, i) => {
        const l = label(f);
        const li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.className = i === active ? 'is-active' : '';
        li.innerHTML = '<svg class="icon" width="16" height="16"><use href="#i-pin"></use></svg><div><strong></strong><small></small></div>';
        li.querySelector('strong').textContent = l.main;
        li.querySelector('small').textContent = l.area;
        li.addEventListener('mousedown', (e) => { e.preventDefault(); pick(i); });
        return li;
      }));
      list.classList.toggle('is-open', items.length > 0);
    };
    const pick = (i) => {
      const f = items[i];
      if (!f) return;
      const l = label(f);
      input.value = [l.main, l.area].filter(Boolean).join(', ');
      close();
      onPick({ lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], address: input.value });
    };
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 3) { close(); return; }
      timer = setTimeout(async () => {
        const b = getBias();
        try {
          const r = await fetch(`${PHOTON}/api/?q=${encodeURIComponent(q)}&limit=6&lang=en&bbox=${NG_BBOX}&lat=${b[0]}&lon=${b[1]}`);
          const j = await r.json();
          items = j.features || [];
          active = -1;
          render();
        } catch (_) { close(); }
      }, 280);
    });
    input.addEventListener('keydown', (e) => {
      if (!list.classList.contains('is-open')) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % items.length; render(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + items.length) % items.length; render(); }
      if (e.key === 'Enter') { e.preventDefault(); pick(active < 0 ? 0 : active); }
      if (e.key === 'Escape') close();
    });
    input.addEventListener('blur', () => setTimeout(close, 120));
  }

  /* =====================================================================
     Booking page
     ===================================================================== */
  const booking = $('[data-dz-booking]');
  if (booking) {
    const cities = JSON.parse(booking.dataset.cities);
    let city = 'Lagos';
    const map = makeMap('dz-map', [cities.Lagos.lat, cities.Lagos.lng], cities.Lagos.zoom);
    const state = { mode: new URLSearchParams(location.search).get('mode') === 'chauffeur' ? 'chauffeur' : 'ride',
      pickup: null, dropoff: null, option: null, hours: 3, quote: null, focus: 'pickup' };
    const markers = { pickup: null, dropoff: null };
    let routeLines = [];
    const carsLayer = L.layerGroup().addTo(map);
    const optionsEl = $('[data-options]', booking);
    const bookBtn = $('[data-book]', booking);
    const errEl = $('[data-book-error]', booking);
    const summary = $('[data-route-summary]', booking);

    const setMarker = (kind, p) => {
      if (markers[kind]) markers[kind].setLatLng([p.lat, p.lng]);
      else {
        markers[kind] = L.marker([p.lat, p.lng], { icon: pin(kind), draggable: true, keyboard: false }).addTo(map);
        markers[kind].on('dragend', async () => {
          const ll = markers[kind].getLatLng();
          state[kind] = { lat: ll.lat, lng: ll.lng, address: 'Finding address…' };
          $(`[data-place="${kind}"] input`, booking).value = 'Finding address…';
          const address = await reverse(ll.lat, ll.lng);
          state[kind].address = address;
          $(`[data-place="${kind}"] input`, booking).value = address;
          refresh();
        });
      }
    };
    const fit = () => {
      const pts = [state.pickup, state.dropoff].filter(Boolean).map((p) => [p.lat, p.lng]);
      if (routeLines.length) map.fitBounds(routeLines[1].getBounds(), { padding: [60, 60], paddingTopLeft: window.innerWidth > 980 ? [440, 60] : [40, 40] });
      else if (pts.length === 1) map.setView(pts[0], 15);
    };
    const place = (kind, p, opts = {}) => {
      state[kind] = p;
      setMarker(kind, p);
      if (!opts.silentInput) $(`[data-place="${kind}"] input`, booking).value = p.address;
      if (kind === 'pickup') loadNearby();
      refresh();
    };
    const bias = () => (state.pickup ? [state.pickup.lat, state.pickup.lng] : [cities[city].lat, cities[city].lng]);
    autocomplete($('[data-place="pickup"]', booking), bias, (p) => place('pickup', p, { silentInput: true }));
    autocomplete($('[data-place="dropoff"]', booking), bias, (p) => place('dropoff', p, { silentInput: true }));
    $$('[data-place] input', booking).forEach((i) => i.addEventListener('focus', () => { state.focus = i.closest('[data-place]').dataset.place; }));

    map.on('click', async (e) => {
      const kind = !state.pickup ? 'pickup' : (state.focus === 'pickup' ? 'pickup' : 'dropoff');
      if (kind === 'dropoff' && state.mode === 'chauffeur' && state.focus !== 'dropoff') return;
      const p = { lat: e.latlng.lat, lng: e.latlng.lng, address: 'Finding address…' };
      place(kind, p);
      p.address = await reverse(p.lat, p.lng);
      $(`[data-place="${kind}"] input`, booking).value = p.address;
      if (kind === 'pickup') state.focus = 'dropoff';
    });

    $('[data-locate]', booking).addEventListener('click', () => {
      if (!navigator.geolocation) return;
      const input = $('#dz-pickup');
      input.value = 'Finding you…';
      navigator.geolocation.getCurrentPosition(async (pos) => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude, address: 'Your location' };
        place('pickup', p);
        map.setView([p.lat, p.lng], 15);
        p.address = await reverse(p.lat, p.lng);
        input.value = p.address;
      }, () => { input.value = ''; window.alert('We could not get your location. Search for your pickup instead.'); },
      { enableHighAccuracy: true, timeout: 10000 });
    });
    $('[data-swap]', booking).addEventListener('click', () => {
      if (!state.pickup || !state.dropoff) return;
      const a = state.pickup;
      place('pickup', state.dropoff);
      place('dropoff', a);
    });

    $$('[data-city]', booking).forEach((b) => b.addEventListener('click', () => {
      city = b.dataset.city;
      $$('[data-city]', booking).forEach((x) => x.classList.toggle('is-active', x === b));
      map.setView([cities[city].lat, cities[city].lng], cities[city].zoom);
      loadNearby([cities[city].lat, cities[city].lng]);
    }));

    const setMode = (mode) => {
      state.mode = mode;
      state.option = mode === 'chauffeur' ? 'chauffeur' : null;
      $$('[data-mode]', booking).forEach((t) => { t.classList.toggle('is-active', t.dataset.mode === mode); t.setAttribute('aria-selected', t.dataset.mode === mode); });
      $('[data-mode-blurb]', booking).textContent = mode === 'chauffeur'
        ? 'A vetted chauffeur drives your car, by the hour or for the day.' : 'A driver picks you up in their car.';
      $('[data-chauffeur-opts]', booking).hidden = mode !== 'chauffeur';
      $('[data-drop-label]', booking).textContent = mode === 'chauffeur' ? 'Final stop (optional)' : 'Destination';
      $('#dz-pickup').placeholder = mode === 'chauffeur' ? 'Where is your car?' : 'Search or tap the map';
      refresh();
    };
    $$('[data-mode]', booking).forEach((t) => t.addEventListener('click', () => setMode(t.dataset.mode)));

    const hoursInput = $('[data-hours] input', booking);
    const setHours = (h) => {
      state.hours = Math.max(3, Math.min(12, h));
      hoursInput.value = state.hours;
      $('[data-hours-note]', booking).textContent = state.hours >= 10 ? 'Full day: you get an hour free' : 'Minimum 3 hours · 10 hours is a full day';
      refresh();
    };
    $('[data-hours-dec]', booking).addEventListener('click', () => setHours(state.hours - 1));
    $('[data-hours-inc]', booking).addEventListener('click', () => setHours(state.hours + 1));

    const whenAt = $('[data-when-at]', booking);
    $$('[name=dz-when]', booking).forEach((r) => r.addEventListener('change', () => {
      whenAt.hidden = r.value !== 'later' || !r.checked;
      if (!whenAt.hidden && !whenAt.value) {
        const d = new Date(Date.now() + 2 * 3600 * 1000);
        d.setMinutes(0, 0, 0);
        whenAt.value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      }
      updateButton();
    }));

    async function loadNearby(center) {
      const c = center || (state.pickup ? [state.pickup.lat, state.pickup.lng] : [cities[city].lat, cities[city].lng]);
      try {
        const r = await fetch(`${booking.dataset.nearbyUrl}?lat=${c[0]}&lng=${c[1]}`);
        const j = await r.json();
        carsLayer.clearLayers();
        j.drivers.forEach((d) => L.marker([d.lat, d.lng], { icon: carIcon(d.heading, d.cls), interactive: false, keyboard: false }).addTo(carsLayer));
      } catch (_) { /* ignore */ }
    }

    let quoteSeq = 0;
    async function refresh() {
      errEl.hidden = true;
      if (!state.pickup) { updateButton(); return; }
      const params = new URLSearchParams({ plat: state.pickup.lat, plng: state.pickup.lng, hours: state.hours });
      if (state.dropoff) { params.set('dlat', state.dropoff.lat); params.set('dlng', state.dropoff.lng); }
      const seq = ++quoteSeq;
      optionsEl.classList.add('is-loading');
      try {
        const r = await fetch(`${booking.dataset.quoteUrl}?${params}`);
        const q = await r.json();
        if (seq !== quoteSeq) return;
        state.quote = q;
        drawRoute(q.route);
        renderOptions(q);
        $('[data-map-tip]', booking).hidden = !!(state.pickup && (state.dropoff || state.mode === 'chauffeur'));
        if (optionsEl.children.length) {
          const panel = booking.querySelector('.dz-panel');
          const top = optionsEl.offsetTop - 120;
          if (panel.scrollHeight > panel.clientHeight && panel.scrollTop < top) panel.scrollTo({ top, behavior: 'smooth' });
        }
      } catch (_) {
        errEl.textContent = 'Could not load prices. Check your connection and try again.';
        errEl.hidden = false;
      } finally {
        optionsEl.classList.remove('is-loading');
        updateButton();
      }
    }
    function drawRoute(r) {
      routeLines.forEach((l) => map.removeLayer(l));
      routeLines = [];
      summary.hidden = !r;
      if (!r) { fit(); return; }
      routeLines = [L.polyline(r.coords, routeShadow).addTo(map), L.polyline(r.coords, routeStyle).addTo(map)];
      summary.innerHTML = `<span><svg class="icon" width="15" height="15"><use href="#i-road"></use></svg> ${r.distance_km} km</span><span><svg class="icon" width="15" height="15"><use href="#i-clock"></use></svg> ~${r.duration_min} min with traffic</span>${r.source === 'estimate' ? '<span class="muted">estimated route</span>' : ''}`;
      fit();
    }
    function renderOptions(q) {
      const opts = q.options.filter((o) => (state.mode === 'chauffeur' ? o.kind === 'chauffeur' : o.kind === 'ride'));
      $('[data-quote-empty]', booking).hidden = opts.length > 0;
      if (state.mode === 'ride' && !state.dropoff) {
        $('[data-quote-empty]', booking).hidden = false;
        $('[data-quote-empty] strong', booking).textContent = 'Now choose your destination';
        optionsEl.replaceChildren();
        return;
      }
      if (!state.option || !opts.find((o) => o.key === state.option)) state.option = opts[0] && opts[0].key;
      optionsEl.replaceChildren(...opts.map((o) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'dz-option' + (o.key === state.option ? ' is-active' : '') + (o.drivers ? '' : ' is-unavailable');
        b.setAttribute('role', 'radio');
        b.setAttribute('aria-checked', o.key === state.option);
        const eta = o.eta_min ? `${o.eta_min} min away` : 'No drivers nearby';
        const sub = o.kind === 'chauffeur' ? `${o.hours} h · ${money(o.rate)}/h · ${eta}` : `${o.blurb} · ${eta}`;
        b.innerHTML = `<span class="dz-opt-icon ${o.key}">${o.kind === 'chauffeur'
          ? '<svg class="icon" width="22" height="22"><use href="#i-steering"></use></svg>' : carSvg(o.key)}</span>
          <span class="dz-opt-text"><strong>${o.label}</strong><small></small></span><span class="dz-opt-price">${o.fare_display}</span>`;
        b.querySelector('small').textContent = sub;
        b.addEventListener('click', () => { state.option = o.key; renderOptions(q); updateButton(); });
        return b;
      }));
    }
    function updateButton() {
      const later = $('[name=dz-when]:checked', booking).value === 'later';
      const opt = state.quote && state.quote.options.find((o) => o.key === state.option);
      let text = 'Choose pickup & destination';
      let ok = false;
      if (!state.pickup) text = state.mode === 'chauffeur' ? 'Where is your car?' : 'Set your pickup';
      else if (state.mode === 'ride' && !state.dropoff) text = 'Where are you going?';
      else if (opt && !opt.drivers && !later) text = 'No drivers nearby right now';
      else if (opt) { ok = true; text = `${later ? 'Schedule' : 'Request'} ${opt.label} · ${opt.fare_display}`; }
      bookBtn.disabled = !ok;
      bookBtn.textContent = booking.dataset.authed === '1' || !ok ? text : 'Sign in to book';
    }

    bookBtn.addEventListener('click', async () => {
      if (booking.dataset.authed !== '1') { window.location.href = booking.dataset.loginUrl; return; }
      const later = $('[name=dz-when]:checked', booking).value === 'later';
      const data = {
        option: state.option, pickup_address: state.pickup.address, pickup_lat: state.pickup.lat, pickup_lng: state.pickup.lng,
        hours: state.hours, payment_method: $('[data-pay]', booking).value, notes: $('[data-notes]', booking).value,
      };
      if (state.dropoff) Object.assign(data, { dropoff_address: state.dropoff.address, dropoff_lat: state.dropoff.lat, dropoff_lng: state.dropoff.lng });
      if (later) data.scheduled_for = whenAt.value;
      bookBtn.disabled = true;
      bookBtn.classList.add('is-loading');
      try {
        const res = await postForm(booking.dataset.bookUrl, data);
        window.location.href = res.url;
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
        bookBtn.disabled = false;
        bookBtn.classList.remove('is-loading');
      }
    });

    setMode(state.mode);
    loadNearby();
    setTimeout(() => map.invalidateSize(), 200);
  }

  /* =====================================================================
     Live trip page
     ===================================================================== */
  const tripEl = $('[data-dz-trip]');
  if (tripEl) {
    const t = JSON.parse(tripEl.dataset.dzTrip);
    const map = makeMap('dz-map', t.pickup, 14);
    L.marker(t.pickup, { icon: pin('pickup'), keyboard: false }).addTo(map);
    const bounds = [t.pickup];
    if (t.dropoff) { L.marker(t.dropoff, { icon: pin('dropoff'), keyboard: false }).addTo(map); bounds.push(t.dropoff); }
    if (t.route && t.route.length > 1) { L.polyline(t.route, routeShadow).addTo(map); L.polyline(t.route, routeStyle).addTo(map); t.route.forEach((c) => bounds.push(c)); }
    let approachLine = t.approach && t.approach.length > 1 ? L.polyline(t.approach, approachStyle).addTo(map) : null;
    const padTL = window.innerWidth > 980 ? [440, 60] : [30, 30];
    map.fitBounds(L.latLngBounds(bounds).pad(0.15), { paddingTopLeft: padTL });
    let car = null;
    let lastStatus = t.status;
    let followed = false;
    const ring = $('[data-eta-ring]');
    let etaMax = null;

    const paint = (s) => {
      $('[data-live-label]').textContent = s.scheduled ? 'Booking confirmed' : s.label;
      $('[data-searching]').hidden = s.status !== 'requested';
      const steps = $('[data-steps]');
      steps.replaceChildren(...s.steps.map(([label, st]) => { const li = document.createElement('li'); li.className = st; li.innerHTML = '<span></span>'; li.append(label); return li; }));
      const d = s.driver;
      const dEl = $('[data-driver]');
      if (d && s.status !== 'requested') {
        dEl.hidden = false;
        $('[data-d-name]').textContent = d.name;
        $('[data-d-initials]').textContent = d.initials;
        $('[data-d-rating]').textContent = d.rating ? Number(d.rating).toFixed(2) : 'New';
        $('[data-d-trips]').textContent = d.trips;
        $('[data-d-vehicle]').textContent = d.vehicle;
        $('[data-d-plate]').textContent = d.plate;
        if (d.lat != null && !s.scheduled) {
          if (!car) car = L.marker([d.lat, d.lng], { icon: carIcon(d.heading, 'economy', d.live), zIndexOffset: 1000, keyboard: false }).addTo(map);
          else { car.setIcon(carIcon(d.heading, 'economy', d.live)); glide(car, [d.lat, d.lng]); }
          if (!followed) { followed = true; map.fitBounds(L.latLngBounds([...bounds, [d.lat, d.lng]]).pad(0.1), { paddingTopLeft: padTL }); }
        }
      }
      const etaBox = $('[data-eta]');
      const showEta = ['accepted', 'arrived', 'in_progress'].includes(s.status) && !s.scheduled;
      etaBox.hidden = !showEta;
      if (showEta) {
        const mins = s.eta_s == null ? '–' : Math.max(0, Math.ceil(s.eta_s / 60));
        $('[data-eta-min]').textContent = s.status === 'arrived' ? '0' : mins;
        $('[data-eta-text]').textContent = s.status === 'accepted' ? `${d ? d.name : 'Your driver'} is on the way`
          : s.status === 'arrived' ? `${d ? d.name : 'Your driver'} has arrived` : 'On the way to your destination';
        $('[data-eta-sub]').textContent = s.status === 'arrived' ? `Look for the ${d ? d.vehicle : 'car'}, plate ${d ? d.plate : ''}`
          : s.status === 'in_progress' ? 'Arriving soon' : 'Head to your pickup point';
        if (s.eta_s != null) {
          etaMax = Math.max(etaMax || 0, s.eta_s);
          const frac = etaMax ? 1 - s.eta_s / etaMax : 1;
          ring.style.strokeDashoffset = String(119.4 * (1 - frac));
        }
      }
      const cancelBox = $('[data-cancel-box]');
      if (cancelBox) cancelBox.hidden = !['requested', 'accepted', 'arrived'].includes(s.status);
      if (s.status === 'in_progress' && approachLine) { map.removeLayer(approachLine); approachLine = null; etaMax = null; }
      if (s.status !== lastStatus) {
        if (['completed', 'cancelled', 'no_driver'].includes(s.status)) { window.location.reload(); return; }
        if (s.status === 'accepted' || s.status === 'arrived') etaMax = null;
        lastStatus = s.status;
      }
    };

    let timer = null;
    const poll = async () => {
      try {
        const r = await fetch(t.liveUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
        if (r.ok) paint(await r.json());
      } catch (_) { /* retry next tick */ }
      if (!['completed', 'cancelled', 'no_driver'].includes(lastStatus)) timer = setTimeout(poll, document.hidden ? 8000 : 2500);
    };
    poll();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) { clearTimeout(timer); poll(); } });
  }

  /* =====================================================================
     Driver app
     ===================================================================== */
  const app = $('[data-dz-driver]');
  if (app) {
    const me = JSON.parse(app.dataset.me);
    const centers = { Lagos: [6.5244, 3.3792], Abuja: [9.0579, 7.4951] };
    const start = me.lat != null ? [me.lat, me.lng] : centers[me.city] || centers.Lagos;
    const map = makeMap('dz-map', start, 14);
    const meMarker = L.marker(start, { icon: carIcon(0, 'economy', true), zIndexOffset: 1000, keyboard: false }).addTo(map);
    const toggle = $('[data-online-toggle]');
    const gpsText = $('[data-gps-text]');
    let watchId = null;
    let firstFix = false;
    let lastSent = 0;
    let jobLayers = [];
    let currentTrip = null;

    const sendLocation = (pos) => {
      const { latitude: lat, longitude: lng, heading } = pos.coords;
      meMarker.setLatLng([lat, lng]);
      if (!firstFix) { firstFix = true; if (!currentTrip) map.setView([lat, lng], 15); }
      gpsText.textContent = `Sharing live location · accuracy ${Math.round(pos.coords.accuracy)} m`;
      $('[data-gps]').classList.add('is-on');
      if (Date.now() - lastSent < 4000) return;
      lastSent = Date.now();
      postForm(app.dataset.locationUrl, { lat, lng, heading: heading || '' }).catch(() => {});
    };
    const startGps = () => {
      if (!navigator.geolocation) { gpsText.textContent = 'This browser cannot share location.'; return; }
      gpsText.textContent = 'Waiting for your location…';
      watchId = navigator.geolocation.watchPosition(sendLocation, () => {
        gpsText.textContent = 'Location permission denied: riders will see your last known position.';
        $('[data-gps]').classList.remove('is-on');
      }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    };
    const stopGps = () => { if (watchId != null) navigator.geolocation.clearWatch(watchId); watchId = null; $('[data-gps]').classList.remove('is-on'); };

    $('input', toggle).addEventListener('change', async (e) => {
      const on = e.target.checked;
      toggle.classList.toggle('is-on', on);
      $('[data-online-label]').textContent = on ? 'Online' : 'Offline';
      $('[data-idle-title]').textContent = on ? 'Looking for trips nearby' : "You're offline";
      try { await postForm(app.dataset.onlineUrl, { online: on ? '1' : '0' }); } catch (_) { /* keep UI state */ }
      if (on) startGps(); else { stopGps(); gpsText.textContent = 'Go online to receive trip requests.'; }
    });
    if ($('input', toggle).checked) startGps();

    const ACTIONS = {
      requested: [['decline', 'Decline', 'btn'], ['accept', 'Accept trip', 'btn btn-primary']],
      accepted: [['cancel', 'Cancel', 'btn btn-ghost'], ['arrived', "I've arrived", 'btn btn-dark']],
      arrived: [['cancel', 'Rider no-show', 'btn btn-ghost'], ['start', 'Start trip', 'btn btn-primary']],
      in_progress: [['complete', 'Complete trip', 'btn btn-primary']],
    };
    const drawJob = (trip) => {
      jobLayers.forEach((l) => map.removeLayer(l));
      jobLayers = [L.marker([trip.pickup.lat, trip.pickup.lng], { icon: pin('pickup') }).addTo(map)];
      const pts = [[trip.pickup.lat, trip.pickup.lng], meMarker.getLatLng()];
      if (trip.dropoff) { jobLayers.push(L.marker([trip.dropoff.lat, trip.dropoff.lng], { icon: pin('dropoff') }).addTo(map)); pts.push([trip.dropoff.lat, trip.dropoff.lng]); }
      if (trip.route && trip.route.length > 1) jobLayers.push(L.polyline(trip.route, routeStyle).addTo(map));
      map.fitBounds(L.latLngBounds(pts).pad(0.2), { paddingTopLeft: window.innerWidth > 980 ? [440, 40] : [20, 20] });
    };
    const renderJob = (trip) => {
      const job = $('[data-job]');
      $('[data-idle]').hidden = !!trip;
      job.hidden = !trip;
      if (!trip) { if (currentTrip) { jobLayers.forEach((l) => map.removeLayer(l)); jobLayers = []; } currentTrip = null; return; }
      if (!currentTrip || currentTrip.number !== trip.number) drawJob(trip);
      currentTrip = trip;
      $('[data-job-kind]').textContent = trip.status === 'requested' ? `New ${trip.kind.toLowerCase()} request` : trip.kind;
      $('[data-job-fare]').textContent = trip.fare;
      $('[data-job-pickup]').textContent = trip.pickup.address;
      $('[data-job-pickup-dist]').textContent = trip.pickup_m != null ? `${(trip.pickup_m / 1000).toFixed(1)} km from you` : '';
      $('[data-job-drop-row]').hidden = !trip.dropoff;
      if (trip.dropoff) $('[data-job-drop]').textContent = trip.dropoff.address;
      $('[data-job-meta]').textContent = trip.hours ? `${trip.hours} hours` : `${trip.distance_km} km · ~${trip.duration_min} min`;
      const notes = $('[data-job-notes]');
      notes.hidden = !trip.notes;
      notes.textContent = trip.notes ? `“${trip.notes}”` : '';
      $('[data-job-rider]').textContent = trip.rider;
      $('[data-job-rider-initial]').textContent = (trip.rider || 'R').slice(0, 1);
      const call = $('[data-job-call]');
      call.href = trip.rider_phone ? `tel:${trip.rider_phone}` : '#';
      call.hidden = !trip.rider_phone || trip.status === 'requested';
      const target = trip.status === 'in_progress' && trip.dropoff ? trip.dropoff : trip.pickup;
      $('[data-job-nav]').href = `https://www.google.com/maps/dir/?api=1&destination=${target.lat},${target.lng}`;
      const actions = $('[data-job-actions]');
      actions.replaceChildren(...(ACTIONS[trip.status] || []).map(([act, text, cls]) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = cls;
        b.textContent = text;
        b.addEventListener('click', async () => {
          if (act === 'cancel' && !window.confirm('Cancel this trip?')) return;
          b.disabled = true;
          try { await postForm(trip.action_url, { action: act }); } catch (err) { window.alert(err.message); }
          poll();
        });
        return b;
      }));
    };

    let timer = null;
    const poll = async () => {
      clearTimeout(timer);
      try {
        const r = await fetch(app.dataset.stateUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
        if (r.ok) renderJob((await r.json()).trip);
      } catch (_) { /* retry */ }
      timer = setTimeout(poll, 3000);
    };
    poll();
  }

  /* =====================================================================
     Staff: live operations map
     ===================================================================== */
  const ops = $('[data-dz-ops]');
  if (ops) {
    const map = makeMap('dz-map', [6.5244, 3.3792], 11);
    const layer = L.layerGroup().addTo(map);
    let first = true;
    const STATUS = { requested: 'Finding driver', accepted: 'Driver en route', arrived: 'At pickup', in_progress: 'On trip' };
    const draw = (data) => {
      layer.clearLayers();
      data.drivers.forEach((d) => {
        L.marker([d.lat, d.lng], { icon: carIcon(d.heading, d.cls, d.busy), keyboard: false })
          .bindTooltip(`${d.name} · ${d.vehicle}${d.busy ? ' · on a trip' : ' · available'}`).addTo(layer);
      });
      data.trips.forEach((t) => {
        L.marker(t.pickup, { icon: pin('pickup'), keyboard: false }).bindTooltip(`${t.number} · ${STATUS[t.status] || t.status}`).addTo(layer);
        if (t.dropoff) L.marker(t.dropoff, { icon: pin('dropoff'), keyboard: false }).addTo(layer);
        if (t.route.length > 1) L.polyline(t.route, { ...routeStyle, weight: 4, opacity: .8 }).addTo(layer);
      });
      $('[data-ops-drivers]').textContent = data.drivers.length;
      $('[data-ops-busy]').textContent = data.drivers.filter((d) => d.busy).length;
      $('[data-ops-trips]').textContent = data.trips.length;
      $('[data-ops-list]').replaceChildren(...data.trips.map((t) => {
        const a = document.createElement('a');
        a.href = t.url;
        a.className = 'dz-ops-trip';
        a.innerHTML = '<strong></strong><span></span><small></small>';
        a.querySelector('strong').textContent = t.number;
        a.querySelector('span').textContent = `${STATUS[t.status] || t.status} · ${t.driver || 'no driver yet'}`;
        a.querySelector('small').textContent = t.pickup_address;
        return a;
      }));
      if (first && data.drivers.length) { first = false; }
    };
    $$('[data-ops-city]').forEach((b) => b.addEventListener('click', () => {
      $$('[data-ops-city]').forEach((x) => x.classList.toggle('is-active', x === b));
      map.setView(b.dataset.opsCity === 'Abuja' ? [9.0579, 7.4951] : [6.5244, 3.3792], 11);
    }));
    const poll = async () => {
      try { const r = await fetch(ops.dataset.url, { credentials: 'same-origin' }); if (r.ok) draw(await r.json()); } catch (_) { /* retry */ }
      setTimeout(poll, 4000);
    };
    poll();
  }
})();
