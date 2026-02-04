#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Point Django at the project settings module before command execution.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        # Import lazily so missing Django raises a clear error below.
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Provide a helpful hint when Django isn't importable.
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # Hand off CLI arguments to Django's management command runner.
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    # Script entry point for manage.py commands.
    main()
