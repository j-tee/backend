#!/usr/bin/env python
"""
Quick security check script
Verifies critical security configurations
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()

from django.conf import settings
from django.db import connection
from colorama import init, Fore, Style

init(autoreset=True)

def print_status(check, status, message):
    """Print check status with color"""
    symbol = "✓" if status else "✗"
    color = Fore.GREEN if status else Fore.RED
    print(f"{color}{symbol} {check}: {message}{Style.RESET_ALL}")

def check_environment_security():
    """Check for insecure environment configurations"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("ENVIRONMENT SECURITY CHECK")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    issues = []
    
    # Check DEBUG mode
    if not settings.DEBUG:
        # Production checks
        
        # Check for test keys
        if hasattr(settings, 'PAYSTACK_SECRET_KEY') and 'test' in str(settings.PAYSTACK_SECRET_KEY):
            issues.append("Using Paystack TEST keys in production")
            print_status("Paystack Keys", False, "TEST keys detected in production")
        else:
            print_status("Paystack Keys", True, "Production keys configured")
        
        if hasattr(settings, 'STRIPE_SECRET_KEY') and 'test' in str(settings.STRIPE_SECRET_KEY):
            issues.append("Using Stripe TEST keys in production")
            print_status("Stripe Keys", False, "TEST keys detected in production")
        else:
            print_status("Stripe Keys", True, "Production keys configured")
        
        # Check SSL settings
        if not settings.SECURE_SSL_REDIRECT:
            issues.append("SSL redirect disabled in production")
            print_status("SSL Redirect", False, "Disabled")
        else:
            print_status("SSL Redirect", True, "Enabled")
        
        if not settings.SESSION_COOKIE_SECURE:
            issues.append("Insecure session cookies")
            print_status("Secure Cookies", False, "Session cookies not secure")
        else:
            print_status("Secure Cookies", True, "Enabled")
        
        # Check for default secret key
        if settings.SECRET_KEY == 'django-insecure-qypa%1&zw5yph-(3sogpdy7x((f8!r)npt6s@6%@fw1(10&e9l':
            issues.append("Using default SECRET_KEY")
            print_status("SECRET_KEY", False, "Using default/weak key")
        else:
            print_status("SECRET_KEY", True, "Custom key configured")
    else:
        print_status("Mode", True, "DEBUG mode (development)")
    
    return issues

def check_rls_enabled():
    """Check if Row-Level Security is enabled"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("ROW-LEVEL SECURITY CHECK")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    try:
        with connection.cursor() as cursor:
            # Check if RLS is enabled on critical tables
            cursor.execute("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename IN ('products', 'sales', 'customers', 'stock', 'suppliers')
                ORDER BY tablename;
            """)
            
            tables = cursor.fetchall()
            all_enabled = True
            
            for table, rls_enabled in tables:
                print_status(f"RLS on {table}", rls_enabled, "Enabled" if rls_enabled else "DISABLED")
                if not rls_enabled:
                    all_enabled = False
            
            return [] if all_enabled else ["RLS not enabled on all critical tables"]
    
    except Exception as e:
        print_status("RLS Check", False, f"Error: {str(e)}")
        return ["Could not verify RLS status"]

def check_middleware_installed():
    """Check if security middleware is installed"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("MIDDLEWARE CHECK")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    issues = []
    
    required_middleware = [
        'app.middleware.EnvironmentSecurityMiddleware',
        'app.middleware.BusinessScopingMiddleware',
    ]
    
    for middleware in required_middleware:
        if middleware in settings.MIDDLEWARE:
            print_status(middleware.split('.')[-1], True, "Installed")
        else:
            print_status(middleware.split('.')[-1], False, "NOT INSTALLED")
            issues.append(f"{middleware} not in MIDDLEWARE")
    
    return issues

def check_file_permissions():
    """Check file permissions on sensitive files"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("FILE PERMISSIONS CHECK")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    issues = []
    base_dir = Path(__file__).parent.parent
    
    sensitive_files = [
        '.env.development',
        '.env.production',
    ]
    
    for filename in sensitive_files:
        filepath = base_dir / filename
        if filepath.exists():
            stat = filepath.stat()
            mode = oct(stat.st_mode)[-3:]
            
            # Should be 600 (owner read/write only)
            if mode == '600':
                print_status(filename, True, f"Permissions: {mode}")
            else:
                print_status(filename, False, f"Permissions: {mode} (should be 600)")
                issues.append(f"{filename} has insecure permissions")
        else:
            print_status(filename, True, "File not found (good if using env vars)")
    
    return issues

def check_gitignore():
    """Check if sensitive files are in .gitignore"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("GITIGNORE CHECK")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    issues = []
    base_dir = Path(__file__).parent.parent
    gitignore = base_dir / '.gitignore'
    
    if not gitignore.exists():
        print_status(".gitignore", False, "File not found")
        return [".gitignore not found"]
    
    with open(gitignore) as f:
        content = f.read()
    
    required_patterns = ['.env', '*.env', '.env.*']
    
    for pattern in required_patterns:
        if pattern in content:
            print_status(f"Pattern: {pattern}", True, "Found in .gitignore")
        else:
            print_status(f"Pattern: {pattern}", False, "NOT in .gitignore")
            issues.append(f"Pattern '{pattern}' not in .gitignore")
    
    return issues

def check_ai_features():
    """Check AI features security"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("AI FEATURES SECURITY CHECK")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    issues = []
    
    # Check if budget caps are configured
    if hasattr(settings, 'AI_BUDGET_CAPS'):
        print_status("Budget Caps", True, "Configured")
    else:
        print_status("Budget Caps", False, "NOT configured")
        issues.append("AI_BUDGET_CAPS not in settings")
    
    # Check if OpenAI key is set
    if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
        print_status("OpenAI Key", True, "Configured")
    else:
        print_status("OpenAI Key", False, "NOT configured")
        issues.append("OPENAI_API_KEY not set")
    
    return issues

def main():
    """Run all security checks"""
    print(f"\n{Fore.YELLOW}{'='*60}")
    print("POS BACKEND SECURITY AUDIT")
    print(f"{'='*60}{Style.RESET_ALL}")
    
    all_issues = []
    
    # Run checks
    all_issues.extend(check_environment_security())
    all_issues.extend(check_rls_enabled())
    all_issues.extend(check_middleware_installed())
    all_issues.extend(check_file_permissions())
    all_issues.extend(check_gitignore())
    all_issues.extend(check_ai_features())
    
    # Summary
    print(f"\n{Fore.CYAN}{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    if not all_issues:
        print(f"{Fore.GREEN}✓ All security checks passed!{Style.RESET_ALL}")
        return 0
    else:
        print(f"{Fore.RED}✗ {len(all_issues)} security issues found:{Style.RESET_ALL}\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
        print(f"\n{Fore.YELLOW}Please address these issues before deploying to production.{Style.RESET_ALL}")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Audit cancelled.{Style.RESET_ALL}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Fore.RED}Error during audit: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)
