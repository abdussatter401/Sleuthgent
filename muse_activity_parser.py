import argparse, csv, glob, json, os, re, sys
from collections import defaultdict

def scrub_thinking(s):
    if not isinstance(s, str):
        return s
    return re.sub(r'"thinking"\s*:\s*"(?:[^"\\]|\\.)*"',
                  '"thinking":"[withheld per dataset policy]"', s)

def norm_text(s):
    if not isinstance(s, str):
        return ''
    return re.sub(r'\s+', ' ', s).strip()

def loc(file, line=None, rowid=None):
    d = {'file': file}
    if line is not None: d['line'] = line
    if rowid is not None: d['rowid'] = rowid
    return d

def load_android(android_dir):
    runs = {}
    for mpath in sorted(glob.glob(os.path.join(android_dir, '*', 'messages.json'))):
        run_id = os.path.basename(os.path.dirname(mpath))
        msgs = json.load(open(mpath, encoding='utf-8'))
        tpath = os.path.join(os.path.dirname(mpath), 'threads.json')
        threads = json.load(open(tpath, encoding='utf-8')) if os.path.exists(tpath) else []
        recs = []
        for x in msgs:
            msg = x.get('message') or {}
            try:
                plain = json.loads(x.get('plaintext_utf8') or '{}')
                content = plain.get('content', '')
            except (json.JSONDecodeError, TypeError, AttributeError):
                content = ''
            recs.append({
                'run_id': run_id, 'rowid': x.get('rowid'),
                'session_id': x.get('session_id'), 'seq': x.get('seq'),
                'role': x.get('role'), 'timestamp_ms': x.get('timestamp'),
                'message_id': msg.get('id'), 'content': content,
                'gcm_authenticated': x.get('gcm_authenticated'),
                'metadata_mismatches': x.get('metadata_mismatches'),
                'attachments': msg.get('attachments', []),
                'widgets': msg.get('widgets', []),
                'presentations': msg.get('presentations', []),
                'segments': msg.get('segments', []),
                'is_synthetic_presentation_carrier': msg.get('isSyntheticPresentationCarrier'),
                'send_status': msg.get('sendStatus'),
                'locator': loc(mpath, rowid=x.get('rowid')),
                '_raw': x,
            })
        recs.sort(key=lambda r: (r['timestamp_ms'] or 0, r['seq'] or 0))
        runs[run_id] = {'messages': recs, 'threads': threads,
                        'threads_path': tpath, 'messages_path': mpath}
    return runs

def load_manifest(path):
    m = json.load(open(path, encoding='utf-8'))
    turns = {}
    for t in m.get('turns', []):
        turns[t['turn_id']] = {
            'turn_id': t['turn_id'], 'role': t.get('role'),
            'content': t.get('content'), 'source': t.get('source'),
            'created_at': t.get('created_at'), 'channels': t.get('channels'),
            'resources': t.get('resources'),
            'locator': loc(path),
            '_raw': t,
        }
    return turns, {'exported_at': m.get('exported_at'), 'file_name': m.get('file_name')}

def load_transcripts(agents_dir):
    sessions = []
    for jpath in sorted(glob.glob(os.path.join(agents_dir, 'agent-*', 'sessions', '*.jsonl'))):
        base = os.path.basename(jpath)
        if base == 'sessions.json':
            continue
        header, items = None, []
        with open(jpath, encoding='utf-8') as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    items.append({'_parse_error': True, 'line': ln,
                                  'locator': loc(jpath, line=ln)})
                    continue
                if d.get('type') == 'session_header':
                    header = d
                elif d.get('type') == 'compaction_checkpoint':
                    items.append({'kind': 'compaction_checkpoint', 'seq': None,
                                  'line': ln, 'raw': d,
                                  'locator': loc(jpath, line=ln)})
                elif 'item' in d:
                    items.append({'kind': 'item', 'seq': d.get('seq'),
                                  'line': ln, 'source': d.get('source'),
                                  'created_at': d.get('created_at'),
                                  'item': d['item'],
                                  'locator': loc(jpath, line=ln)})
                else:
                    items.append({'kind': 'unrecognized', 'seq': None,
                                  'line': ln, 'raw': d,
                                  'locator': loc(jpath, line=ln)})
        items.sort(key=lambda r: (r.get('seq') is None, r.get('seq') or 0))
        sid = (header or {}).get('session_id') or base.replace('.jsonl', '')
        sessions.append({'session_id': sid, 'path': jpath, 'header': header,
                         'items': items})
    return sessions

def load_run_index(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    return {r['run_id']: r for r in rows}

def extract_approval(output_text):
    if not isinstance(output_text, str):
        return []
    out = []
    for m in re.finditer(
            r'userConfirmationRequired[\\]*"[\\]*:[\\]*"?(\w+)[\\]*"?,'
            r'[\\]*"userConfirmationStatus[\\]*"[\\]*:[\\]*"([a-z_]+)', output_text):
        out.append({'required': m.group(1) == 'true', 'status': m.group(2)})
    if not out:
        for m in re.finditer(r'userConfirmationStatus[\\]*"[\\]*:[\\]*"([a-z_]+)',
                             output_text):
            out.append({'required': None, 'status': m.group(1)})
    return out

def analyze_transcript(sess):
    turns, cur = [], None
    pending = {}
    stats = {'thinking_blocks': 0, 'tool_calls': 0, 'tool_outputs': 0,
             'commentary': 0, 'assistant_messages': 0, 'developer_messages': 0,
             'user_messages': 0, 'approvals': []}
    for rec in sess['items']:
        if rec.get('kind') != 'item':
            continue
        it, line = rec['item'], rec['line']
        kind = it.get('type')
        if kind == 'message':
            role = it.get('role')
            if role == 'user':
                stats['user_messages'] += 1
                if cur: turns.append(cur)
                cur = {'user_text': scrub_thinking(it.get('text', '')), 'user_seq': rec['seq'],
                       'user_line': line, 'user_created_at': rec['created_at'],
                       'actions': [], 'locator': rec['locator']}
            elif role == 'assistant':
                stats['assistant_messages'] += 1
                act = {'kind': 'assistant_message', 'seq': rec['seq'],
                       'text': scrub_thinking(it.get('text', '')), 'locator': rec['locator']}
                if cur:
                    cur['actions'].append(act)
                else:
                    turns.append({'user_text': None, 'user_seq': None,
                                  'user_line': None, 'user_created_at': None,
                                  'actions': [act], 'android_links': [],
                                  'locator': rec['locator']})
            else:
                stats['developer_messages'] += 1
        elif kind == 'thinking':
            stats['thinking_blocks'] += 1
            a = {'kind': 'thinking', 'seq': rec['seq'],
                 'content': '[withheld per dataset policy]',
                 'locator': rec['locator']}
            if cur: cur['actions'].append(a)
        elif kind == 'commentary_text':
            stats['commentary'] += 1
            a = {'kind': 'commentary', 'seq': rec['seq'],
                 'text': scrub_thinking(it.get('text', '')), 'locator': rec['locator']}
            if cur: cur['actions'].append(a)
        elif kind == 'function_call':
            stats['tool_calls'] += 1
            try:
                args = json.loads(it['arguments']) if isinstance(it.get('arguments'), str) else it.get('arguments')
            except (json.JSONDecodeError, TypeError):
                args = {'_raw': it.get('arguments')}
            a = {'kind': 'tool_call', 'seq': rec['seq'], 'name': it.get('name'),
                 'call_id': it.get('call_id'), 'arguments': args,
                 'output': None, 'approvals': [], 'locator': rec['locator']}
            pending[it.get('call_id')] = a
            if cur: cur['actions'].append(a)
        elif kind == 'function_call_output':
            stats['tool_outputs'] += 1
            appr = extract_approval(it.get('output', ''))
            for x in appr:
                stats['approvals'].append({**x, 'seq': rec['seq'],
                                           'line': line, 'session_id': sess['session_id']})
            o = {'seq': rec['seq'], 'success': it.get('success'),
                 'output_length': len(str(it.get('output', ''))),
                 'locator': rec['locator']}
            if it.get('call_id') in pending:
                pending[it['call_id']]['output'] = o
                pending[it['call_id']]['approvals'] = appr
        else:
            a = {'kind': 'unknown:' + str(kind), 'seq': rec['seq'],
                 'locator': rec['locator']}
            if cur: cur['actions'].append(a)
    if cur: turns.append(cur)
    turns = [t for t in turns if isinstance(t, dict) and 'actions' in t]
    return {'turns': turns, 'stats': stats}

def build_content_index(android_runs):
    idx = defaultdict(list)
    for run_id, rd in android_runs.items():
        for m in rd['messages']:
            c = norm_text(m['content'])
            if c:
                idx[c].append((run_id, m['message_id'], m['role']))
    return idx

def link_turns(sessions_analyzed, content_index):
    for sess in sessions_analyzed:
        for t in sess['turns']:
            if not t.get('user_text'):
                continue
            hits = content_index.get(norm_text(t['user_text']), [])
            t['android_links'] = [
                {'run_id': r, 'message_id': mid, 'role': role,
                 'confidence': 'high-exact-text-match'} for r, mid, role in hits]
    return sessions_analyzed

def main(argv=None):
    ap = argparse.ArgumentParser(description='Reconstruct user/agent activity')
    ap.add_argument('--android', required=True)
    ap.add_argument('--transcripts', required=True)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--run-index', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    android = load_android(a.android)
    manifest_turns, manifest_meta = load_manifest(a.manifest)
    sessions = load_transcripts(a.transcripts)
    run_index = load_run_index(a.run_index)

    android_ids = set()
    for rd in android.values():
        android_ids.update(m['message_id'] for m in rd['messages'] if m['message_id'])
    manifest_ids = set(manifest_turns)
    join_audit = {'android_ids': len(android_ids), 'manifest_ids': len(manifest_ids),
                  'overlap': len(android_ids & manifest_ids)}

    analyzed = []
    for s in sessions:
        an = analyze_transcript(s)
        an['session_id'] = s['session_id']
        an['path'] = s['path']
        an['header'] = s['header']
        analyzed.append(an)
    analyzed = link_turns(analyzed, build_content_index(android))

    index = []
    for an in analyzed:
        sid = an['session_id']
        out = {'session_id': sid, 'header': an['header'],
               'stats': an['stats'], 'turns': an['turns'],
               'grouping_note': ('Turns are positional: a user message owns the '
                                 'actions after it (by seq) up to the next user '
                                 'message. This is a heuristic, not a recorded '
                                 'relationship. Thinking content withheld per '
                                 'dataset policy.')}
        p = os.path.join(a.out, f'session_{sid}.json')
        json.dump(out, open(p, 'w', encoding='utf-8'), indent=2,
                  ensure_ascii=False, default=str)
        linked_runs = sorted({l['run_id'] for t in an['turns']
                              for l in t.get('android_links', [])})
        index.append({'session_id': sid,
                      'user_messages': an['stats']['user_messages'],
                      'tool_calls': an['stats']['tool_calls'],
                      'approvals': len(an['stats']['approvals']),
                      'linked_android_runs': linked_runs,
                      'file': os.path.basename(p)})

    for run_id, rd in android.items():
        recs = []
        for m in rd['messages']:
            tid = m['message_id']
            mt = manifest_turns.get(tid)
            recs.append({
                'message_id': tid, 'role': m['role'], 'timestamp_ms': m['timestamp_ms'],
                'seq': m['seq'], 'session_id': m['session_id'],
                'content': m['content'],
                'manifest_turn': ({'turn_id': mt['turn_id'], 'created_at': mt['created_at'],
                                   'channels': mt['channels']} if mt else None),
                'attachments': m['attachments'], 'widgets': m['widgets'],
                'presentations': m['presentations'],
                'send_status': m['send_status'],
                'gcm_authenticated': m['gcm_authenticated'],
                'metadata_mismatches': m['metadata_mismatches'],
                'locator': m['locator'],
            })
        json.dump({'run_id': run_id,
                   'run_meta': run_index.get(run_id, {}),
                   'threads': rd['threads'],
                   'messages': recs,
                   'ordering_note': 'ordered by (timestamp_ms, seq); rowid is not chronology'},
                  open(os.path.join(a.out, f'android_{run_id}.json'), 'w', encoding='utf-8'),
                  indent=2, ensure_ascii=False, default=str)

    json.dump({'sessions': index, 'manifest_join_audit': join_audit,
               'manifest_meta': manifest_meta,
               'run_index': run_index},
              open(os.path.join(a.out, 'index.json'), 'w', encoding='utf-8'),
              indent=2, ensure_ascii=False, default=str)

    n_turns = sum(len(an['turns']) for an in analyzed)
    n_approvals = sum(len(an['stats']['approvals']) for an in analyzed)
    print(f'{len(analyzed)} sessions, {n_turns} turns, {n_approvals} explicit approvals; '
          f'manifest<->android id overlap {join_audit["overlap"]}/{join_audit["manifest_ids"]}')
    print('wrote', a.out)

if __name__ == '__main__':
    main()
