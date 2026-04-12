import urllib.request
import json
import sys

req = urllib.request.Request(
    'https://api.github.com/repos/NAVEEN2422008/EV_charging/actions/runs?per_page=1',
    headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'python'}
)
try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    run = data['workflow_runs'][0]
    
    jobs_url = run['jobs_url']
    req2 = urllib.request.Request(jobs_url, headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'python'})
    res2 = urllib.request.urlopen(req2)
    jobs_data = json.loads(res2.read())
    
    for job in jobs_data['jobs']:
        if job['conclusion'] == 'failure':
            print(f"Failed Job: {job['name']} (ID: {job['id']})")
            # Try to get annotations
            try:
                ann_req = urllib.request.Request(
                    f"https://api.github.com/repos/NAVEEN2422008/EV_charging/check-runs/{job['id']}/annotations",
                    headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'python'}
                )
                ann_res = urllib.request.urlopen(ann_req)
                annotations = json.loads(ann_res.read())
                for ann in annotations:
                    print(f"Annotation: {ann.get('path')} [{ann.get('annotation_level')}]: {ann.get('message')}")
            except Exception as e:
                print(f"Could not load annotations: {e}")
                
except Exception as e:
    print(f"Error: {e}")
