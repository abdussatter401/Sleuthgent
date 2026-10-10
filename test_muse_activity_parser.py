import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from muse_activity_parser import (
    load_android, load_manifest, load_transcripts, analyze_transcript,
    extract_approval, link_turns, build_content_index, norm_text,
    scrub_thinking)

fails = 0
def check(name, cond, extra=''):
    global fails
    print(('ok ' if cond else 'FAIL ') + name, extra)
    if not cond: fails += 1

def write(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if isinstance(obj, str): open(p, 'w').write(obj)
    else: json.dump(obj, open(p, 'w'))

def main():
    with tempfile.TemporaryDirectory() as d:
        ad = os.path.join(d, 'android', 'RUN1')
        msgs = [
            {'rowid': 99, 'session_id': 's1', 'seq': 2, 'role': 'AGENT',
             'timestamp': 2000, 'gcm_authenticated': True,
             'plaintext_utf8': json.dumps({'content': 'reply text'}),
             'message': {'id': 'assistant-msg-aaa', 'role': 'AGENT',
                         'attachments': [], 'widgets': [{'w': 1}]},
             'metadata_mismatches': []},
            {'rowid': 5, 'session_id': 's1', 'seq': 1, 'role': 'USER',
             'timestamp': 1000, 'gcm_authenticated': True,
             'plaintext_utf8': json.dumps({'content': 'do the thing'}),
             'message': {'id': 'user-msg-bbb', 'role': 'USER'},
             'metadata_mismatches': []},
        ]
        write(os.path.join(ad, 'messages.json'), msgs)
        write(os.path.join(ad, 'threads.json'), [{'session_id': 's1'}])
        android = load_android(os.path.join(d, 'android'))
        ms = android['RUN1']['messages']
        check('android ordered by timestamp not rowid',
              [m['role'] for m in ms] == ['USER', 'AGENT'])
        check('widgets preserved', ms[1]['widgets'] == [{'w': 1}])
        check('locator has rowid', ms[0]['locator']['rowid'] == 5)

        mp = os.path.join(d, 'manifest.json')
        write(mp, {'exported_at': 't', 'file_name': 'f', 'turns': [
            {'turn_id': 'assistant-msg-aaa', 'role': 'assistant',
             'content': 'reply text', 'created_at': 't', 'channels': ['main'],
             'resources': []}]})
        turns, meta = load_manifest(mp)
        check('manifest loaded', 'assistant-msg-aaa' in turns)

        td = os.path.join(d, 'agents', 'agent-x', 'sessions')
        jl = '\n'.join([
            json.dumps({'type': 'session_header', 'session_id': 'sess1'}),
            json.dumps({'type': 'item', 'seq': 0, 'source': 'runtime',
                        'created_at': 't0',
                        'item': {'type': 'message', 'role': 'user', 'text': 'do the thing'}}),
            json.dumps({'type': 'item', 'seq': 1, 'source': 'runtime',
                        'created_at': 't1',
                        'item': {'type': 'thinking', 'thinking': 'SECRET PLAN', 'signature': 's'}}),
            json.dumps({'type': 'item', 'seq': 2, 'source': 'runtime',
                        'created_at': 't2',
                        'item': {'type': 'function_call', 'call_id': 'c1',
                                 'name': 'exec', 'arguments': '{"cmd":"ls"}'}}),
            json.dumps({'type': 'item', 'seq': 3, 'source': 'runtime',
                        'created_at': 't3',
                        'item': {'type': 'function_call_output', 'call_id': 'c1',
                                 'output': '{\"userConfirmationRequired\":true,\"userConfirmationStatus\":\"approved\"}',
                                 'success': True}}),
            json.dumps({'type': 'item', 'seq': 4, 'source': 'runtime',
                        'created_at': 't4',
                        'item': {'type': 'message', 'role': 'assistant', 'text': 'reply text'}}),
            json.dumps({'type': 'weird', 'x': 1}),
            'not json at all',
        ])
        write(os.path.join(td, 'abc.jsonl'), jl)
        sessions = load_transcripts(os.path.join(d, 'agents'))
        check('1 session loaded', len(sessions) == 1)
        check('unrecognized + parse-error surfaced',
              any(r['kind'] == 'unrecognized' for r in sessions[0]['items']) and
              any(r.get('_parse_error') for r in sessions[0]['items']))

        an = analyze_transcript(sessions[0])
        check('1 turn', len(an['turns']) == 1)
        t = an['turns'][0]
        check('user text kept', t['user_text'] == 'do the thing')
        kinds = [x['kind'] for x in t['actions']]
        check('thinking/tool/assistant in turn',
              kinds == ['thinking', 'tool_call', 'assistant_message'], str(kinds))
        check('thinking content NOT reproduced',
              all('SECRET' not in json.dumps(x) for x in t['actions']))
        call = next(x for x in t['actions'] if x['kind'] == 'tool_call')
        check('call paired by call_id',
              call['output'] is not None and call['output']['success'] is True)
        check('approval extracted explicitly',
              call['approvals'] == [{'required': True, 'status': 'approved'}])
        check('stats approvals', len(an['stats']['approvals']) == 1)

        check('no approval inferred from plain output',
              extract_approval('plain ok output') == [])

        idx = build_content_index(android)
        link_turns([an], idx)
        check('turn linked to android by content',
              t['android_links'] and
              t['android_links'][0]['message_id'] == 'user-msg-bbb' and
              t['android_links'][0]['confidence'] == 'high-exact-text-match')

        check('norm collapses whitespace', norm_text('a\n b') == 'a b')

        dirty = 'dispatch [EXECUTE] {"type":"thinking","thinking":"SECRET PLAN \\"quoted\\" here"} end'
        clean = scrub_thinking(dirty)
        check('embedded thinking scrubbed',
              'SECRET PLAN' not in clean and '[withheld per dataset policy]' in clean
              and clean.startswith('dispatch [EXECUTE]') and clean.endswith(' end'),
              clean[:80])
    print('ALL PASS' if fails == 0 else f'{fails} FAILURES')
    return fails

if __name__ == '__main__':
    sys.exit(1 if main() else 0)
