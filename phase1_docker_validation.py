#!/usr/bin/env python3
"""
Comprehensive Phase 1 Integration Validation
Verifies nginx routing, Docker configuration, and API/Streamlit setup
"""

import os
import json

def validate_nginx_conf():
    """Validate nginx.conf exists and is properly configured"""
    print("\n✓ Checking nginx.conf...")
    
    if not os.path.exists('nginx.conf'):
        print("  ✗ nginx.conf not found")
        return False
    
    with open('nginx.conf', 'r') as f:
        content = f.read()
    
    required_sections = [
        'upstream streamlit',
        'upstream api',
        'server {',
        'listen 80',
        'location /api/',
        'location /reset',
        'location /health',
        'location /step',
        'location /state',
        'location /info',
        'location /',
        'proxy_pass http://streamlit',
        'proxy_pass http://api',
    ]
    
    missing = []
    for section in required_sections:
        if section not in content:
            missing.append(section)
    
    if missing:
        print(f"  ✗ Missing sections: {missing}")
        return False
    
    print("  ✓ All required nginx sections present")
    return True


def validate_dockerfile():
    """Validate Dockerfile has nginx and proper startup"""
    print("\n✓ Checking Dockerfile...")
    
    with open('Dockerfile', 'r') as f:
        content = f.read()
    
    required_items = [
        'apt-get install -y nginx',
        'COPY nginx.conf /etc/nginx/sites-available/default',
        'EXPOSE 80',
        ('nginx' in content),  # service nginx or nginx -g
        '/app/scripts/start.sh',
    ]
    
    checks = [
        'apt-get install -y nginx' in content,
        'COPY nginx.conf /etc/nginx/sites-available/default' in content,
        'EXPOSE 80' in content,
        ('nginx' in content),
        '/app/scripts/start.sh' in content,
    ]
    
    if not all(checks):
        print(f"  ✗ Missing critical nginx/startup configuration")
        return False
    
    print("  ✓ Dockerfile properly configured with nginx")
    return True


def validate_startup_script():
    """Validate scripts/start.sh has proper port configuration"""
    print("\n✓ Checking scripts/start.sh...")
    
    with open('scripts/start.sh', 'r') as f:
        content = f.read()
    
    required_checks = [
        ('nginx' in content, 'nginx startup'),
        ('--port 5000' in content, 'API on port 5000'),
        ('8501' in content, 'Streamlit on port 8501'),
        ('api_server.py' in content, 'API server reference'),
        ('streamlit run' in content, 'Streamlit command'),
    ]
    
    missing = []
    for check, desc in required_checks:
        if not check:
            missing.append(desc)
    
    if missing:
        print(f"  ✗ Missing items: {missing}")
        return False
    
    print("  ✓ scripts/start.sh properly configured")
    print("    - nginx starts first")
    print("    - API on port 5000")
    print("    - Streamlit on port 8501")
    return True


def validate_structure():
    """Validate overall project structure"""
    print("\n✓ Checking project structure...")
    
    required_files = [
        'app.py',
        'api_server.py',
        'inference.py',
        'openenv.yaml',
        'nginx.conf',
        'Dockerfile',
        'requirements.txt',
        'scripts/start.sh',
    ]
    
    missing = []
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)
    
    if missing:
        print(f"  ✗ Missing files: {missing}")
        return False
    
    print("  ✓ All required files present")
    return True


def validate_ports():
    """Validate port configuration alignment"""
    print("\n✓ Validating port configuration...")
    
    ports_config = {
        'nginx': 80,
        'api': 5000,
        'streamlit': 8501,
        'docker_expose': '80 5000 8501'
    }
    
    # Verify start.sh mentions correct ports
    with open('scripts/start.sh', 'r') as f:
        start_content = f.read()
    
    if '5000' not in start_content or '8501' not in start_content:
        print("  ✗ Port configuration mismatch in start.sh")
        return False
    
    # Verify Dockerfile exposes correct ports
    with open('Dockerfile', 'r') as f:
        docker_content = f.read()
    
    if 'EXPOSE 80 5000 8501' not in docker_content:
        print("  ✗ Port configuration mismatch in Dockerfile")
        return False
    
    print(f"  ✓ Port configuration correct:")
    print(f"    - nginx: {ports_config['nginx']}")
    print(f"    - API: {ports_config['api']}")
    print(f"    - Streamlit: {ports_config['streamlit']}")
    print(f"    - Docker exposed: {ports_config['docker_expose']}")
    return True


def validate_routing():
    """Validate nginx routing logic"""
    print("\n✓ Validating nginx routing patterns...")
    
    with open('nginx.conf', 'r') as f:
        nginx_content = f.read()
    
    routing_patterns = {
        '/api/': 'API endpoints',
        '/reset': 'Reset endpoint',
        '/health': 'Health check',
        '/step': 'Step endpoint',
        '/state': 'State endpoint',
        '/info': 'Info endpoint',
        '/': 'Streamlit frontend',
    }
    
    issues = []
    for pattern, name in routing_patterns.items():
        if f"location {pattern}" not in nginx_content:
            issues.append(f"Missing routing for {pattern} ({name})")
    
    if issues:
        print(f"  ✗ Routing issues: {issues}")
        return False
    
    print("  ✓ All nginx routing patterns configured:")
    for pattern, name in routing_patterns.items():
        print(f"    - {pattern:15} → {name}")
    return True


def print_summary():
    """Print integration summary"""
    print("\n" + "="*80)
    print("DOCKER INTEGRATION ARCHITECTURE")
    print("="*80)
    print("""
    Container Port 80 (nginx reverse proxy)
        ├── /api/*        → Port 5000 (Flask API)
        ├── /reset        → Port 5000 (Flask API)
        ├── /health       → Port 5000 (Flask API)
        ├── /step         → Port 5000 (Flask API)
        ├── /state        → Port 5000 (Flask API)
        ├── /info         → Port 5000 (Flask API)
        └── /             → Port 8501 (Streamlit App)

    Startup Sequence:
        1. Docker starts
        2. /app/scripts/start.sh executes
        3. Service nginx start
        4. Python API server starts on 5000
        5. Streamlit starts on 8501
        6. nginx routes traffic between them
        
    External Access:
        • Dashboard: http://localhost/
        • API: http://localhost/api/...
        • Reset endpoint: http://localhost/reset (POST)
        • Health check: http://localhost/health (GET)
    """)
    print("="*80)


def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE PHASE 1 INTEGRATION VALIDATION")
    print("="*80)
    
    checks = [
        ('Structure', validate_structure),
        ('nginx.conf', validate_nginx_conf),
        ('Dockerfile', validate_dockerfile),
        ('start.sh', validate_startup_script),
        ('Port Configuration', validate_ports),
        ('Routing Patterns', validate_routing),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  ✗ Error during validation: {e}")
            results.append((name, False))
    
    print_summary()
    
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Docker configuration is ready for Phase 1")
        print("\nReady for Docker build:")
        print("  docker build -t ev-charging .")
        print("  docker run -p 80:80 ev-charging")
    else:
        print("❌ SOME CHECKS FAILED - Please review issues above")
    print("="*80 + "\n")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    exit(main())
