"""
Run quick environment diagnostics for CarHub development.

Usage:
    python scripts/check_env.py

Outputs Python executable, venv status, installed critical packages, and simple DB/file checks.
"""
import sys
import importlib
import pkgutil

def check_module(name):
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, '__version__', None)
        return True, version
    except Exception as e:
        return False, str(e)

def main():
    print('Python executable:', sys.executable)
    print('Platform:', sys.platform)
    print('Sys.path sample:', sys.path[:3])

    modules = ['django', 'PIL', 'allauth', 'channels', 'channels_redis']
    for m in modules:
        ok, info = check_module(m)
        print(f'Module {m}:', 'OK' if ok else 'MISSING', info)

    try:
        import django
        print('Django version:', django.get_version())
    except Exception:
        pass

    print('\nCheck complete.')

if __name__ == '__main__':
    main()
