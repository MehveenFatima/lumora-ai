import urllib.request
import json
import time
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _api_auth  # noqa: E402,F401  (signs in and authenticates every API request)

base = 'http://localhost:3000/api/v1/workspaces/ws_computer_networks/quizzes'

# 1. Create quiz session via proxy
t0 = time.time()
req = urllib.request.Request(
    base,
    data=json.dumps({'target_question_count': 5}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req, timeout=10) as resp:
    s_data = json.loads(resp.read().decode())
t_create = time.time() - t0
session_id = s_data['id']
print(f"Proxy Create Session: {t_create*1000:.1f}ms (Session ID: {session_id})")

# 2. Get first question
t0 = time.time()
q_id = s_data['current_question']['id']
with urllib.request.urlopen(f'{base}/{session_id}/questions/{q_id}', timeout=10) as resp:
    q_data = json.loads(resp.read().decode())
t_q = time.time() - t0
print(f"Proxy Fetch Question: {t_q*1000:.1f}ms")

# 3. Submit attempt for question
t0 = time.time()
sub_req = urllib.request.Request(
    f'{base}/{session_id}/questions/{q_id}/attempt',
    data=json.dumps({'selected_option': 'B', 'response_time_ms': 1200}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(sub_req, timeout=10) as resp:
    att_data = json.loads(resp.read().decode())
t_att = time.time() - t0
print(f"Proxy Submit Attempt: {t_att*1000:.1f}ms (is_correct={att_data.get('is_correct')})")

# 4. Measure next-batch latency via Next.js proxy
batch_req = urllib.request.Request(
    f'{base}/{session_id}/next-batch',
    data=json.dumps({'batch_size': 5}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
t0 = time.time()
with urllib.request.urlopen(batch_req, timeout=10) as resp:
    batch_data = json.loads(resp.read().decode())
t_next_batch = time.time() - t0
print(f"Proxy Next-Batch Latency: {t_next_batch*1000:.1f}ms (Round: {batch_data.get('adaptation_round')}, Stage: {batch_data.get('current_adaptation_stage')})")
assert t_next_batch < 5.0, f"Next batch too slow: {t_next_batch:.2f}s"
print("SUCCESS: Browser-facing Next.js proxy quiz path verified under 5.0s!")
