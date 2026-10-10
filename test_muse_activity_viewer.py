import json
import os
import tempfile

from muse_activity_viewer import DataError, EvidenceStore


def write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(value, handle)


def main():
    with tempfile.TemporaryDirectory() as directory:
        session_id = 'session-one'
        session_file = f'session_{session_id}.json'
        write(os.path.join(directory, 'index.json'), {
            'sessions': [{
                'session_id': session_id, 'user_messages': 1, 'tool_calls': 1,
                'approvals': 1, 'linked_android_runs': ['RUN1'], 'file': session_file,
            }],
            'manifest_join_audit': {'android_ids': 2, 'manifest_ids': 2, 'overlap': 1},
            'manifest_meta': {}, 'run_index': {'RUN1': {}},
        })
        write(os.path.join(directory, session_file), {
            'session_id': session_id,
            'stats': {
                'thinking_blocks': 1, 'assistant_messages': 1,
                'approvals': [{'status': 'approved'}],
            },
            'turns': [{
                'user_text': 'Find evidence',
                'actions': [{
                    'kind': 'tool_call', 'name': 'search',
                    'arguments': {'query': 'needle'},
                }],
            }],
        })
        write(os.path.join(directory, 'android_RUN1.json'), {
            'run_id': 'RUN1', 'run_meta': {}, 'ordering_note': 'ordered',
            'messages': [
                {'message_id': 'm1', 'role': 'USER', 'content': 'Find evidence',
                 'manifest_turn': {'turn_id': 'm1'}, 'gcm_authenticated': True},
                {'message_id': 'm2', 'role': 'AGENT', 'content': 'Found it',
                 'manifest_turn': None, 'gcm_authenticated': True},
            ],
        })

        store = EvidenceStore(directory)
        assert store.summary()['sessions'] == 1
        assert store.summary()['tool_calls'] == 1
        assert store.list_sessions({'q': ['needle']})['total'] == 1
        assert store.list_sessions({'approval': ['approved']})['total'] == 1
        assert store.list_sessions({'approval': ['declined']})['total'] == 0
        assert store.get_session(session_id)['session_id'] == session_id
        assert store.list_android_messages('RUN1', {'role': ['USER']})['total'] == 1
        assert store.list_android_messages('RUN1', {'joined': ['no']})['total'] == 1
        try:
            store.get_session('missing')
        except DataError:
            pass
        else:
            raise AssertionError('Unknown session should raise DataError')

    print('ALL PASS')


if __name__ == '__main__':
    main()
