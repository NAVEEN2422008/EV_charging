import urllib.request
import json

req = urllib.request.Request(
    'https://api.github.com/repos/NAVEEN2422008/EV_charging/actions/runs?per_page=1',
    headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'python'}
)
try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    run = data['workflow_runs'][0]
    
    print(f"Run ID: {run['id']}, Status: {run['status']}, Conclusion: {run['conclusion']}")
    
    if run['status'] == 'completed' and run['conclusion'] != 'success':
        jobs_url = run['jobs_url']
        req2 = urllib.request.Request(jobs_url, headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'python'})
        res2 = urllib.request.urlopen(req2)
        jobs_data = json.loads(res2.read())
        for job in jobs_data['jobs']:
            if job['conclusion'] == 'failure':
                print(f"Failed Job: {job['name']} (ID: {job['id']})")
                for step in job['steps']:
                    if step['conclusion'] == 'failure':
                        print(f"  Failed Step: {step['name']}")
except Exception as e:
    print(f"Error: {e}")
