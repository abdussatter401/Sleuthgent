'use strict';

const state = {
  androidRuns: [],
  sessionPage: 1,
  selectedSession: null,
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

function shortId(value, length = 14) {
  if (!value) return '—';
  const text = String(value);
  return text.length > length ? `${text.slice(0, length)}…` : text;
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
  if (!data.turns.length) turns.append(errorBlock('This provider session contains no reconstructed turns.'));
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
    body.append(codeBlock('Call and result metadata', {
      call_id: action.call_id,
      output: action.output || 'No paired output metadata',
      explicit_approvals: action.approvals || [],
    }));
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

function debounce(callback, delay = 250) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), delay);
  };
}

function bindEvents() {
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
}

function populateRunSelector() {
  const selector = document.getElementById('session-run');
  state.androidRuns.forEach(run => selector.append(new Option(run.run_id, run.run_id)));
}

async function init() {
  bindEvents();
  try {
    const android = await api('/api/android');
    state.androidRuns = android.items;
    populateRunSelector();
    await loadSessions();
    document.getElementById('loading').classList.add('hidden');
  } catch (error) {
    document.getElementById('loading').classList.add('hidden');
    showError(error);
  }
}

init();
