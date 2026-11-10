"""Register an actual demo endpoint. Does not fabricate telemetry, ML or AI."""
import argparse
import json
import os
import urllib.request
parser = argparse.ArgumentParser()
parser.add_argument('--base-url', default='http://127.0.0.1:8001')
args = parser.parse_args()
base = args.base_url.rstrip('/')
headers = {'Content-Type':'application/json'}
if os.environ.get('ISMS_ADMIN_TOKEN'): headers['Authorization'] = 'Bearer ' + os.environ['ISMS_ADMIN_TOKEN']
payload = {'service_name':'ISMS demo endpoint', 'url':base+'/demo/health', 'timeout':3, 'response_time_threshold':500}
request = urllib.request.Request(base+'/api/v1/services', data=json.dumps(payload).encode(), headers=headers, method='POST')
with urllib.request.urlopen(request, timeout=15) as response:
    service = json.load(response)
print('Registered real demo endpoint:', service['service_id'])
print('Telemetry will be collected by actual checks. No AI responses or training samples were seeded.')
