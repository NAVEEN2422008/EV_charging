import subprocess
import sys

runs = 50
failed = 0
for i in range(runs):
    res = subprocess.run(['python', '-m', 'pytest', 'tests/', '-q', '--tb=short'], capture_output=True, text=True)
    if res.returncode != 0:
        print(f'\nRun {i} FAILED:')
        print(res.stdout)
        failed += 1
        break
    else:
        sys.stdout.write('.')
        sys.stdout.flush()

if failed == 0:
    print('\nAll 50 passes!')
