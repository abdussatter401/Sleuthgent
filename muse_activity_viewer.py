import argparse
import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


class DataError(Exception):
    pass


def _read_json(path):
    try:
        with path.open(encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f'Cannot read {path}: {exc}') from exc


def _integer(value, default, minimum=1, maximum=None):
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    result = max(minimum, result)
    return min(result, maximum) if maximum is not None else result


class EvidenceStore:
    def __init__(self, output_dir):
        self.root = Path(output_dir).expanduser().resolve()
        self.index_path = self.root / 'index.json'
        if not self.index_path.is_file():
            raise DataError(f'No index.json found in {self.root}')
        self.index = _read_json(self.index_path)
        self.sessions = {}
        self.session_summaries = []
        self.android = {}
        self._load_sessions()
        self._discover_android_runs()

    def _safe_output_path(self, filename):
        if Path(filename).name != filename:
            raise DataError(f'Unsafe output filename: {filename}')
        path = (self.root / filename).resolve()
        if path.parent != self.root:
            raise DataError(f'Output escaped data directory: {filename}')
        return path

    def _load_sessions(self):
        for record in self.index.get('sessions', []):
            session_id = str(record.get('session_id', ''))
            filename = record.get('file', '')
            if not session_id or not filename:
                continue
            document = _read_json(self._safe_output_path(filename))
            self.sessions[session_id] = document
            stats = document.get('stats', {})
            turns = document.get('turns', [])
            approvals = stats.get('approvals', [])
            approval_statuses = sorted({
                str(item.get('status')) for item in approvals if item.get('status')
            })
            search_parts = [session_id]
            action_kinds = set()
            tool_names = set()
            for turn in turns:
                search_parts.append(str(turn.get('user_text') or ''))
                for action in turn.get('actions', []):
                    kind = str(action.get('kind') or 'unknown')
                    action_kinds.add(kind)
                    search_parts.append(str(action.get('text') or ''))
                    if kind == 'tool_call' and action.get('name'):
                        tool_names.add(str(action['name']))
                        search_parts.append(str(action['name']))
                        search_parts.append(json.dumps(
                            action.get('arguments'), ensure_ascii=False, default=str))
            summary = {
                **record,
                'turns': len(turns),
                'thinking_blocks': stats.get('thinking_blocks', 0),
                'assistant_messages': stats.get('assistant_messages', 0),
                'approval_statuses': approval_statuses,
                'action_kinds': sorted(action_kinds),
                'tool_names': sorted(tool_names),
                '_search': ' '.join(search_parts).casefold(),
            }
            self.session_summaries.append(summary)

    def _discover_android_runs(self):
        for path in sorted(self.root.glob('android_*.json')):
            document = _read_json(path)
            run_id = str(document.get('run_id') or path.stem.removeprefix('android_'))
            messages = document.get('messages', [])
            roles = {}
            joined = 0
            authenticated = 0
            for message in messages:
                role = str(message.get('role') or 'UNKNOWN')
                roles[role] = roles.get(role, 0) + 1
                joined += message.get('manifest_turn') is not None
                authenticated += message.get('gcm_authenticated') is True
            self.android[run_id] = {
                'document': document,
                'summary': {
                    'run_id': run_id,
                    'messages': len(messages),
                    'roles': roles,
                    'manifest_joined': joined,
                    'gcm_authenticated': authenticated,
                    'file': path.name,
                    'run_meta': document.get('run_meta', {}),
                },
            }

    def summary(self):
        sessions = self.session_summaries
        return {
            'data_directory': str(self.root),
            'sessions': len(sessions),
            'turns': sum(item.get('turns', 0) for item in sessions),
            'user_messages': sum(item.get('user_messages', 0) for item in sessions),
            'tool_calls': sum(item.get('tool_calls', 0) for item in sessions),
            'approvals': sum(item.get('approvals', 0) for item in sessions),
            'linked_sessions': sum(bool(item.get('linked_android_runs')) for item in sessions),
            'android_runs': [item['summary'] for item in self.android.values()],
            'manifest_join_audit': self.index.get('manifest_join_audit', {}),
            'manifest_meta': self.index.get('manifest_meta', {}),
            'run_count': len(self.index.get('run_index', {})),
            'policies': {
                'thinking_withheld': True,
                'approval_source': 'explicit records only',
                'turn_grouping': 'positional heuristic',
                'android_ordering': '(timestamp_ms, seq)',
            },
        }

    def list_sessions(self, params):
        query = params.get('q', [''])[0].strip().casefold()
        run_id = params.get('run', [''])[0]
        approval = params.get('approval', ['all'])[0]
        sort = params.get('sort', ['session_id'])[0]
        page = _integer(params.get('page', [1])[0], 1)
        page_size = _integer(params.get('page_size', [30])[0], 30, maximum=100)
        records = self.session_summaries
        if query:
            records = [item for item in records if query in item['_search']]
        if run_id:
            records = [item for item in records if run_id in item.get('linked_android_runs', [])]
        if approval == 'any':
            records = [item for item in records if item.get('approvals', 0) > 0]
        elif approval == 'none':
            records = [item for item in records if item.get('approvals', 0) == 0]
        elif approval not in ('', 'all'):
            records = [item for item in records
                       if approval in item.get('approval_statuses', [])]
        reverse = sort in ('tool_calls', 'turns', 'approvals', 'user_messages')
        if sort == 'linked':
            records = sorted(records, key=lambda item: (
                not bool(item.get('linked_android_runs')), item['session_id']))
        else:
            key = sort if sort in {
                'session_id', 'tool_calls', 'turns', 'approvals', 'user_messages'
            } else 'session_id'
            records = sorted(records, key=lambda item: item.get(key, 0), reverse=reverse)
        total = len(records)
        start = (page - 1) * page_size
        public_records = [
            {key: value for key, value in item.items() if key != '_search'}
            for item in records[start:start + page_size]
        ]
        return {
            'items': public_records,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': max(1, (total + page_size - 1) // page_size),
        }

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise DataError(f'Unknown session: {session_id}') from exc

    def list_android_runs(self):
        return {'items': [item['summary'] for item in self.android.values()]}

    def list_android_messages(self, run_id, params):
        if run_id not in self.android:
            raise DataError(f'Unknown Android run: {run_id}')
        document = self.android[run_id]['document']
        query = params.get('q', [''])[0].strip().casefold()
        role = params.get('role', ['all'])[0]
        joined = params.get('joined', ['all'])[0]
        page = _integer(params.get('page', [1])[0], 1)
        page_size = _integer(params.get('page_size', [40])[0], 40, maximum=100)
        messages = document.get('messages', [])
        if query:
            messages = [message for message in messages if query in (
                f"{message.get('message_id', '')} {message.get('session_id', '')} "
                f"{message.get('content', '')}".casefold())]
        if role not in ('', 'all'):
            messages = [message for message in messages if message.get('role') == role]
        if joined == 'yes':
            messages = [message for message in messages
                        if message.get('manifest_turn') is not None]
        elif joined == 'no':
            messages = [message for message in messages
                        if message.get('manifest_turn') is None]
        total = len(messages)
        start = (page - 1) * page_size
        return {
            'run_id': run_id,
            'run_meta': document.get('run_meta', {}),
            'ordering_note': document.get('ordering_note'),
            'items': messages[start:start + page_size],
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': max(1, (total + page_size - 1) // page_size),
        }


def make_handler(store, web_dir):
    class ViewerHandler(BaseHTTPRequestHandler):
        server_version = 'MuseActivityViewer/1.0'

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path.startswith('/api/'):
                    self._handle_api(parsed)
                else:
                    self._handle_static(parsed.path)
            except DataError as exc:
                self._json({'error': str(exc)}, 404)
            except Exception as exc:
                self.log_error('Unhandled request error: %s', exc)
                self._json({'error': 'Internal viewer error'}, 500)

        def _handle_api(self, parsed):
            params = parse_qs(parsed.query)
            path = parsed.path.rstrip('/')
            if path == '/api/summary':
                self._json(store.summary())
            elif path == '/api/sessions':
                self._json(store.list_sessions(params))
            elif path.startswith('/api/sessions/'):
                session_id = unquote(path.removeprefix('/api/sessions/'))
                self._json(store.get_session(session_id))
            elif path == '/api/android':
                self._json(store.list_android_runs())
            elif path.startswith('/api/android/'):
                run_id = unquote(path.removeprefix('/api/android/'))
                self._json(store.list_android_messages(run_id, params))
            else:
                self._json({'error': 'Unknown API endpoint'}, 404)

        def _handle_static(self, request_path):
            relative = request_path.lstrip('/') or 'index.html'
            if not re.fullmatch(r'[A-Za-z0-9._/-]+', relative) or '..' in relative.split('/'):
                self.send_error(404)
                return
            path = (web_dir / relative).resolve()
            if path.parent != web_dir and web_dir not in path.parents:
                self.send_error(404)
                return
            if not path.is_file():
                path = web_dir / 'index.html'
            content = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(content)

        def _json(self, payload, status=200):
            content = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(content)

        def _security_headers(self):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header(
                'Content-Security-Policy',
                "default-src 'self'; img-src 'self' data:; style-src 'self'; "
                "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
            )

        def log_message(self, message, *args):
            print(f'{self.address_string()} - {message % args}')

    return ViewerHandler


def main(argv=None):
    parser = argparse.ArgumentParser(description='Browse Muse parser output locally')
    parser.add_argument('--data', default='parsed_data', help='Parser output directory')
    parser.add_argument('--host', default='127.0.0.1', help='Bind address (default: local only)')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)

    store = EvidenceStore(args.data)
    web_dir = (Path(__file__).resolve().parent / 'viewer_web').resolve()
    if not (web_dir / 'index.html').is_file():
        parser.error(f'Viewer assets not found in {web_dir}')
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store, web_dir))
    print(f'Muse Activity Viewer: http://{args.host}:{args.port}')
    print(f'Data: {store.root}')
    print('Press Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping viewer')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
