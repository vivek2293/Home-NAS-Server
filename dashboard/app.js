/**
 * app.js — Add a new entry here to add a card to the dashboard.
 *
 * Fields:
 *   id   – unique element ID for the anchor (useful for testing/automation)
 *   name – display name
 *   desc – one-line outcome-focused description shown on the card
 *   icon – emoji icon
 *   port – port number used to build the service URL
 *   tag  – short category label shown in the badge (user-facing, not the port)
 */
const SERVICES = [
  {
    id: 'qbittorrent-link',
    name: 'qBittorrent',
    desc: 'Add and monitor your downloads',
    icon: '⬇️',
    port: 8043,
    tag: 'Downloads',
  },
  {
    id: 'jellyfin-link',
    name: 'Jellyfin',
    desc: 'Stream movies, shows, and music',
    icon: '🎬',
    port: 8096,
    tag: 'Media',
  },
];

/* ── Build one card using DOM methods (no innerHTML — avoids XSS) ── */
function createCard(svc, protocol, hostname) {
  const card = document.createElement('a');
  card.id = svc.id;
  card.href = `${protocol}//${hostname}:${svc.port}`;
  card.className = 'card';
  card.target = '_blank';
  card.rel = 'noopener noreferrer'; // always suppress Referer to all services

  const icon = document.createElement('div');
  icon.className = 'card__icon';
  icon.textContent = svc.icon;

  const body = document.createElement('div');
  body.className = 'card__body';

  const name = document.createElement('span');
  name.className = 'card__name';
  name.textContent = svc.name;

  const desc = document.createElement('span');
  desc.className = 'card__desc';
  desc.textContent = svc.desc;

  const badge = document.createElement('span');
  badge.className = 'card__badge';
  badge.textContent = svc.tag;

  body.append(name, desc, badge);

  // Arrow SVG — built via DOM so it is never parsed as user-controlled HTML
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'card__arrow');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M7 17L17 7M7 7h10v10');
  svg.appendChild(path);

  card.append(icon, body, svg);
  return card;
}

/* ── Build the page ── */
(function init() {
  const { protocol, hostname } = window.location;

  // Populate dynamic hostname labels
  document.querySelectorAll('[data-hostname]').forEach(el => {
    el.textContent = hostname;
  });

  // Render cards
  const grid = document.getElementById('services-grid');
  SERVICES.forEach(svc => {
    // Validate port before touching the DOM or building URLs
    if (!Number.isInteger(svc.port) || svc.port < 1 || svc.port > 65535) {
      console.warn(`[dashboard] Skipping "${svc.name}": invalid port "${svc.port}"`);
      return;
    }
    grid.appendChild(createCard(svc, protocol, hostname));
  });

  // Mouse-tracking glow on every card (single delegated listener)
  grid.addEventListener('mousemove', e => {
    const card = e.target.closest('.card');
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100).toFixed(1) + '%');
    card.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100).toFixed(1) + '%');
  });
})();

