'use strict';

const state = {
  summary: null,
  androidRuns: [],
  sessionPage: 1,
  sessionPages: 1,
  selectedSession: null,
  androidPage: 1,
  androidPages: 1,
};

const viewMeta = {
  overview: ['CASE OVERVIEW', 'Activity reconstruction'],
  sessions: ['PROVIDER TRANSCRIPTS', 'Session investigation'],
  android: ['DEVICE EVIDENCE', 'Android activity'],
  methodology: ['INTERPRETATION GUIDE', 'Reconstruction methodology'],
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function clear(node) {
  node.replaceChildren();
  return node;
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function formatTime(timestamp) {
  if (!timestamp) return 'No timestamp';
  const date = new Date(Number(timestamp));
  if (Number.isNaN(date.valueOf())) return String(timestamp);
  return date.toLocaleString([], {
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function shortId(value, length = 14) {
  if (!value) return '—';
  const text = String(value);
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function percent(part, total) {
  return total ? Math.round((part / total) * 1000) / 10 : 0;
}

async function api(path, params) {
  const query = params ? `?${new URLSearchParams(params)}` : '';
  const response = await fetch(`${path}${query}`, {headers: {'Accept': 'application/json'}});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

function showError(error) {
  const banner = document.getElementById('error-banner');
  banner.textContent = error.message || String(error);
  banner.classList.remove('hidden');
}

function toast(message) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.classList.add('show');
  window.setTimeout(() => node.classList.remove('show'), 1800);
}

async function copyText(text, label = 'Copied') {
  try {
    await navigator.clipboard.writeText(text);
    toast(label);
  } catch {
    toast('Clipboard access unavailable');
  }
}

function switchView(name) {
  document.querySelectorAll('.view').forEach(node => node.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(node => node.classList.remove('active'));
  document.getElementById(`${name}-view`).classList.add('active');
  document.querySelector(`.nav-item[data-view="${name}"]`).classList.add('active');
  document.getElementById('view-eyebrow').textContent = viewMeta[name][0];
  document.getElementById('view-title').textContent = viewMeta[name][1];
  document.querySelector('.sidebar').classList.remove('open');
  if (name === 'sessions') loadSessions();
  if (name === 'android') loadAndroidMessages();
}

function metricCard(label, value, detail) {
  const card = element('article', 'metric');
  card.append(element('span', 'label', label));
  card.append(element('strong', '', formatNumber(value)));
  card.append(element('small', '', detail));
  return card;
}

function renderOverview() {
  const summary = state.summary;
  const cards = clear(document.getElementById('summary-cards'));
  cards.append(
    metricCard('Provider sessions', summary.sessions, `${summary.linked_sessions} linked to device evidence`),
    metricCard('Reconstructed turns', summary.turns, 'Positional grouping heuristic'),
    metricCard('User messages', summary.user_messages, 'Provider-side transcript records'),
    metricCard('Tool calls', summary.tool_calls, 'Typed function-call records'),
    metricCard('Explicit approvals', summary.approvals, 'No inferred approvals'),
  );

  const audit = summary.manifest_join_audit;
  const coverage = percent(audit.overlap, audit.manifest_ids);
  const coverageRoot = clear(document.getElementById('join-coverage'));
  const wrap = element('div', 'coverage-wrap');
  const donut = element('div', 'donut');
  donut.style.setProperty('--percent', coverage);
  const donutLabel = element('div', 'donut-label');
  donutLabel.append(element('strong', '', `${coverage}%`), element('span', '', 'manifest IDs matched'));
  donut.append(donutLabel);
  const details = element('div', 'coverage-details');
  [
    ['Manifest IDs matched', audit.overlap, audit.manifest_ids],
    ['Manifest IDs unmatched', audit.manifest_ids - audit.overlap, audit.manifest_ids],
    ['Unique Android IDs', audit.android_ids, audit.android_ids],
  ].forEach(([label, value, total]) => {
    const row = element('div', 'coverage-stat');
    row.append(element('span', '', label), element('strong', '', `${formatNumber(value)} / ${formatNumber(total)}`));
    const bar = element('div', 'bar');
    const fill = element('i');
    fill.style.width = `${percent(value, total)}%`;
    bar.append(fill);
    row.append(bar);
    details.append(row);
  });
  wrap.append(donut, details);
  coverageRoot.append(wrap);

  const source = clear(document.getElementById('source-coverage'));
  const sourceList = element('div', 'source-list');
  const androidMessages = summary.android_runs.reduce((total, run) => total + run.messages, 0);
  const sourceRows = [
    ['Run index entries', summary.run_count],
    ['Android evidence runs', summary.android_runs.length],
    ['Device messages', androidMessages],
    ['Provider sessions', summary.sessions],
    ['Manifest turns', audit.manifest_ids],
  ];
  sourceRows.forEach(([label, value]) => {
    const row = element('div', 'source-row');
    row.append(element('span', '', label), element('strong', '', formatNumber(value)));
    sourceList.append(row);
  });
  source.append(sourceList);

  const policies = clear(document.getElementById('policy-list'));
  [
    ['✓', 'Private thinking content is withheld.'],
    ['✓', 'Approvals require explicit confirmation records.'],
    ['△', 'Turn grouping is a positional heuristic.'],
    ['✓', 'Android chronology uses timestamp and sequence.'],
  ].forEach(([icon, text]) => {
    const item = element('div', 'policy-item');
    item.append(element('b', '', icon), element('span', '', text));
    policies.append(item);
  });
}

async function renderNotableSessions() {
  const data = await api('/api/sessions', {sort: 'tool_calls', page_size: 6});
  const root = clear(document.getElementById('notable-sessions'));
  const header = element('div', 'table-row header');
  ['Session', 'Turns', 'Tools', 'Approvals', 'Device'].forEach(text => header.append(element('span', '', text)));
  root.append(header);
  data.items.forEach(item => {
    const row = element('div', 'table-row');
    const button = element('button', 'session-link', item.session_id);
    button.title = item.session_id;
    button.addEventListener('click', () => openSessionFromOverview(item.session_id));
    row.append(
      button,
      element('span', '', item.turns),
      element('span', '', item.tool_calls),
      element('span', '', item.approvals),
      element('span', item.linked_android_runs.length ? 'link-chip' : '', item.linked_android_runs.length ? 'Linked' : '—'),
    );
    root.append(row);
  });
}

async function openSessionFromOverview(sessionId) {
  switchView('sessions');
  await selectSession(sessionId);
}

function sessionParams() {
  return {
    q: document.getElementById('session-search').value,
    run: document.getElementById('session-run').value,
    approval: document.getElementById('session-approval').value,
    sort: document.getElementById('session-sort').value,
    page: state.sessionPage,
    page_size: 30,
  };
}

async function loadSessions() {
  try {
    const data = await api('/api/sessions', sessionParams());
    state.sessionPages = data.pages;
    state.sessionPage = Math.min(state.sessionPage, data.pages);
    document.getElementById('session-result-count').textContent = `${formatNumber(data.total)} sessions`;
    document.getElementById('session-page-label').textContent = `Page ${data.page} of ${data.pages}`;
    const list = clear(document.getElementById('session-list'));
    if (!data.items.length) {
      const empty = element('div', 'empty-state');
      empty.append(element('span', '', '⌕'), element('h2', '', 'No matching sessions'), element('p', '', 'Change the filters or try a broader search term.'));
      list.append(empty);
    }
    data.items.forEach(item => {
      const button = element('button', 'session-item');
      if (item.session_id === state.selectedSession) button.classList.add('active');
      button.dataset.sessionId = item.session_id;
      button.append(element('span', 'session-id', item.session_id));
      const meta = element('span', 'session-item-meta');
      meta.append(
        metadata(`${item.turns} turns`),
        metadata(`${item.tool_calls} tools`),
        metadata(`${item.approvals} approvals`, item.approvals ? 'approval-chip' : ''),
      );
      if (item.linked_android_runs.length) meta.append(metadata(item.linked_android_runs.join(', '), 'link-chip'));
      button.append(meta);
      button.addEventListener('click', () => selectSession(item.session_id));
      list.append(button);
    });
    renderPagination(document.getElementById('session-pagination'), data.page, data.pages, page => {
      state.sessionPage = page;
      loadSessions();
    });
  } catch (error) {
    showError(error);
  }
}

function metadata(text, className = '') {
  const node = element('span', className);
  node.append(element('b', '', text));
  return node;
}

function renderPagination(root, page, pages, callback) {
  clear(root);
  if (pages <= 1) return;
  const previous = element('button', '', '←');
  previous.disabled = page <= 1;
  previous.addEventListener('click', () => callback(page - 1));
  root.append(previous);
  const start = Math.max(1, page - 2);
  const end = Math.min(pages, page + 2);
  for (let number = start; number <= end; number += 1) {
    const button = element('button', number === page ? 'active' : '', number);
    button.addEventListener('click', () => callback(number));
    root.append(button);
  }
  const next = element('button', '', '→');
  next.disabled = page >= pages;
  next.addEventListener('click', () => callback(page + 1));
  root.append(next);
}

async function selectSession(sessionId) {
  state.selectedSession = sessionId;
  document.querySelectorAll('.session-item').forEach(node => {
    node.classList.toggle('active', node.dataset.sessionId === sessionId);
  });
  const detail = document.getElementById('session-detail');
  clear(detail).append(loadingBlock('Loading session…'));
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
    renderSessionDetail(data);
  } catch (error) {
    clear(detail).append(errorBlock(error.message));
  }
}

function loadingBlock(text) {
  const root = element('div', 'empty-state');
  root.append(element('div', 'spinner'), element('p', '', text));
  return root;
}

function errorBlock(text) {
  const root = element('div', 'empty-state');
  root.append(element('span', '', '!'), element('h2', '', 'Unable to load evidence'), element('p', '', text));
  return root;
}

function renderSessionDetail(data) {
  const detail = clear(document.getElementById('session-detail'));
  const header = element('div', 'detail-header');
  const top = element('div', 'detail-header-top');
  const title = element('div');
  title.append(element('p', 'eyebrow', 'PROVIDER SESSION'), element('h2', '', data.session_id));
  const copy = element('button', 'copy-button', 'Copy session JSON');
  copy.addEventListener('click', () => copyText(JSON.stringify(data, null, 2), 'Session JSON copied'));
  top.append(title, copy);
  header.append(top);
  const stats = element('div', 'detail-stats');
  stats.append(
    badge(`${data.turns.length} turns`, 'blue'),
    badge(`${data.stats.tool_calls || 0} tool calls`, 'green'),
    badge(`${(data.stats.approvals || []).length} approvals`, (data.stats.approvals || []).length ? 'amber' : ''),
    badge(`${data.stats.thinking_blocks || 0} withheld thinking blocks`, ''),
  );
  header.append(stats);
  detail.append(header);
  if (data.grouping_note) detail.append(element('div', 'grouping-note', data.grouping_note));
  const turns = element('div', 'turn-list');
  data.turns.forEach((turn, index) => turns.append(renderTurn(turn, index)));
  if (!data.turns.length) {
    turns.append(errorBlock('This provider session contains no reconstructed turns.'));
  }
  detail.append(turns);
}

function badge(text, color) {
  return element('span', `badge ${color}`.trim(), text);
}

function renderTurn(turn, index) {
  const root = element('section', 'turn');
  root.append(element('span', 'turn-marker'));
  const heading = element('div', 'turn-heading');
  heading.append(element('strong', '', `Turn ${index + 1}`), element('span', '', `user seq ${turn.user_seq ?? '—'} · ${turn.user_created_at || 'time unavailable'}`));
  root.append(heading);
  root.append(element('div', 'user-prompt', turn.user_text || '[No preceding user message]'));
  if (turn.android_links && turn.android_links.length) {
    const links = element('div', 'android-links');
    turn.android_links.forEach(link => {
      const chip = badge(`${link.run_id} · ${shortId(link.message_id)} · ${link.confidence}`, 'blue');
      chip.title = link.message_id || '';
      links.append(chip);
    });
    root.append(links);
  }
  const actions = element('div', 'action-list');
  (turn.actions || []).forEach(action => actions.append(renderAction(action)));
  root.append(actions);
  if (turn.locator) root.append(locatorRow(turn.locator));
  return root;
}

function renderAction(action) {
  const details = element('details', 'action');
  const summary = element('summary');
  let kindText = action.kind || 'unknown';
  let kindClass = '';
  let name = '';
  if (action.kind === 'tool_call') name = action.name || 'unnamed tool';
  else if (action.kind === 'assistant_message') {
    kindText = 'assistant';
    kindClass = 'assistant';
    name = shortPreview(action.text);
  } else if (action.kind === 'thinking') {
    kindClass = 'thinking';
    name = 'Content withheld by dataset policy';
  } else if (action.kind === 'commentary') name = shortPreview(action.text);
  summary.append(
    element('span', `action-kind ${kindClass}`.trim(), kindText.replaceAll('_', ' ')),
    element('span', 'action-name', name),
    element('span', 'seq', `seq ${action.seq ?? '—'}`),
  );
  details.append(summary);
  const body = element('div', 'action-body');
  if (action.kind === 'tool_call') {
    body.append(codeBlock('Arguments', action.arguments));
    const callMeta = {
      call_id: action.call_id,
      output: action.output || 'No paired output metadata',
      explicit_approvals: action.approvals || [],
    };
    body.append(codeBlock('Call and result metadata', callMeta));
  } else if (action.kind === 'thinking') {
    body.append(element('p', '', 'A private reasoning block was recorded at this sequence position. Its content is not reproduced.'));
  } else if (action.text !== undefined) {
    body.append(element('p', '', action.text || '[Empty text]'));
  } else {
    body.append(codeBlock('Recorded fields', action));
  }
  if (action.locator) body.append(locatorRow(action.locator));
  details.append(body);
  return details;
}

function shortPreview(value) {
  const text = String(value || '').replaceAll(/\s+/g, ' ').trim();
  return text.length > 90 ? `${text.slice(0, 90)}…` : text;
}

function codeBlock(label, value) {
  const wrapper = element('div');
  wrapper.append(element('p', 'eyebrow', label));
  const pre = element('pre');
  pre.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  wrapper.append(pre);
  return wrapper;
}

function locatorRow(locator) {
  const row = element('div', 'locator');
  const parts = [locator.file];
  if (locator.line !== undefined) parts.push(`line ${locator.line}`);
  if (locator.rowid !== undefined) parts.push(`rowid ${locator.rowid}`);
  const value = parts.filter(Boolean).join(' · ');
  const text = element('span', '', value);
  text.title = value;
  const copy = element('button', 'text-button', 'Copy locator');
  copy.addEventListener('click', () => copyText(value, 'Locator copied'));
  row.append(text, copy);
  return row;
}

async function loadAndroidMessages() {
  const runId = document.getElementById('android-run').value;
  if (!runId) return;
  const params = {
    q: document.getElementById('android-search').value,
    role: document.getElementById('android-role').value,
    joined: document.getElementById('android-joined').value,
    page: state.androidPage,
    page_size: 40,
  };
  const list = clear(document.getElementById('android-message-list'));
  list.append(loadingBlock('Loading device messages…'));
  try {
    const data = await api(`/api/android/${encodeURIComponent(runId)}`, params);
    state.androidPages = data.pages;
    renderAndroidHeader(data);
    clear(list);
    if (!data.items.length) list.append(errorBlock('No device messages match these filters.'));
    data.items.forEach(message => list.append(renderAndroidMessage(message)));
    renderPagination(document.getElementById('android-pagination'), data.page, data.pages, page => {
      state.androidPage = page;
      loadAndroidMessages();
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
  } catch (error) {
    clear(list).append(errorBlock(error.message));
  }
}

function renderAndroidHeader(data) {
  const root = clear(document.getElementById('android-run-header'));
  const title = element('div');
  title.append(element('h2', '', data.run_id), element('p', '', data.ordering_note || 'Device-side evidence'));
  root.append(title, element('span', 'run-count', `${formatNumber(data.total)} matching messages`));
}

function renderAndroidMessage(message) {
  const role = String(message.role || 'UNKNOWN');
  const root = element('article', `message ${role === 'USER' ? 'user' : 'agent'}`);
  const time = element('div', 'message-time');
  time.append(document.createTextNode(formatTime(message.timestamp_ms)));
  time.append(document.createElement('br'));
  time.append(document.createTextNode(`seq ${message.seq ?? '—'}`));
  const track = element('div', 'message-track');
  track.append(element('span', 'message-dot', role === 'USER' ? 'U' : 'A'));
  const card = element('div', 'message-card');
  const meta = element('div', 'message-meta');
  meta.append(element('strong', '', role));
  if (message.manifest_turn) meta.append(badge('Manifest joined', 'green'));
  else meta.append(badge('No manifest match', ''));
  if (message.gcm_authenticated === true) meta.append(badge('GCM authenticated', 'blue'));
  if (message.metadata_mismatches && message.metadata_mismatches.length) meta.append(badge(`${message.metadata_mismatches.length} metadata mismatch`, 'amber'));
  card.append(meta, element('div', 'message-content', message.content || '[No text content]'));
  const identifiers = element('div', 'message-identifiers');
  const messageId = element('span', '', `message ${message.message_id || '—'}`);
  messageId.title = message.message_id || '';
  const sessionId = element('span', '', `thread ${message.session_id || '—'}`);
  sessionId.title = message.session_id || '';
  identifiers.append(messageId, sessionId);
  if ((message.attachments || []).length) identifiers.append(element('span', '', `${message.attachments.length} attachment(s)`));
  if ((message.widgets || []).length) identifiers.append(element('span', '', `${message.widgets.length} widget(s)`));
  if ((message.presentations || []).length) identifiers.append(element('span', '', `${message.presentations.length} presentation(s)`));
  card.append(identifiers);
  if (message.locator) card.append(locatorRow(message.locator));
  track.append();
  root.append(time, track, card);
  return root;
}

function debounce(callback, delay = 250) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), delay);
  };
}

function bindEvents() {
  document.querySelectorAll('.nav-item').forEach(button => {
    button.addEventListener('click', () => switchView(button.dataset.view));
  });
  document.querySelectorAll('[data-go]').forEach(button => {
    button.addEventListener('click', () => switchView(button.dataset.go));
  });
  document.getElementById('menu-button').addEventListener('click', () => {
    document.querySelector('.sidebar').classList.toggle('open');
  });
  document.getElementById('theme-button').addEventListener('click', () => {
    document.body.classList.toggle('high-contrast');
  });

  const delayedSessions = debounce(() => {
    state.sessionPage = 1;
    loadSessions();
  });
  document.getElementById('session-search').addEventListener('input', delayedSessions);
  ['session-run', 'session-approval', 'session-sort'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
      state.sessionPage = 1;
      loadSessions();
    });
  });

  const delayedAndroid = debounce(() => {
    state.androidPage = 1;
    loadAndroidMessages();
  });
  document.getElementById('android-search').addEventListener('input', delayedAndroid);
  ['android-run', 'android-role', 'android-joined'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
      state.androidPage = 1;
      loadAndroidMessages();
    });
  });
}

function populateRunSelectors() {
  const sessionRun = document.getElementById('session-run');
  const androidRun = document.getElementById('android-run');
  state.androidRuns.forEach(run => {
    sessionRun.append(new Option(run.run_id, run.run_id));
    androidRun.append(new Option(`${run.run_id} (${formatNumber(run.messages)} messages)`, run.run_id));
  });
}

async function init() {
  bindEvents();
  try {
    const [summary, android] = await Promise.all([
      api('/api/summary'),
      api('/api/android'),
    ]);
    state.summary = summary;
    state.androidRuns = android.items;
    populateRunSelectors();
    renderOverview();
    await renderNotableSessions();
    document.getElementById('loading').classList.add('hidden');
  } catch (error) {
    document.getElementById('loading').classList.add('hidden');
    showError(error);
  }
}

init();
