#!/usr/bin/env python3
"""
Simple Authentication for JaxWatch Admin
Uses environment variable ADMIN_PASSWORD for basic authentication
"""

import os
import hashlib
import secrets
from functools import wraps
from flask import request, session, jsonify, redirect, url_for


class SimpleAuth:
    """Basic password-based authentication for admin access"""

    def __init__(self, app=None):
        self.app = app
        self.admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')  # Default for dev

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize authentication with Flask app"""
        app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))

        # Add login/logout routes
        app.add_url_rule('/admin/login', 'admin_login', self.login, methods=['GET', 'POST'])
        app.add_url_rule('/admin/logout', 'admin_logout', self.logout, methods=['POST'])
        app.add_url_rule('/admin/check-auth', 'admin_check_auth', self.check_auth, methods=['GET'])

    def login(self):
        """Handle admin login"""
        if request.method == 'GET':
            # Return login form HTML
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>JaxWatch Admin Login</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
                    .login-form { background: #f5f5f5; padding: 30px; border-radius: 8px; }
                    input { width: 100%; padding: 10px; margin: 10px 0; }
                    button { width: 100%; padding: 10px; background: #007cba; color: white; border: none; cursor: pointer; }
                    .error { color: red; margin-top: 10px; }
                </style>
            </head>
            <body>
                <div class="login-form">
                    <h2>JaxWatch Admin Access</h2>
                    <form method="post">
                        <input type="password" name="password" placeholder="Admin Password" required>
                        <button type="submit">Login</button>
                    </form>
                    {error}
                </div>
            </body>
            </html>
            '''.format(error='<div class="error">Invalid password</div>' if request.args.get('error') else '')

        elif request.method == 'POST':
            password = request.form.get('password')

            if password == self.admin_password:
                session['admin_authenticated'] = True
                session['admin_user'] = 'admin'
                return redirect('/admin.html')
            else:
                return redirect('/admin/login?error=1')

    def logout(self):
        """Handle admin logout"""
        session.pop('admin_authenticated', None)
        session.pop('admin_user', None)
        return jsonify({"status": "logged_out"})

    def check_auth(self):
        """Check if user is authenticated"""
        return jsonify({
            "authenticated": session.get('admin_authenticated', False),
            "user": session.get('admin_user')
        })

    def is_authenticated(self):
        """Check if current session is authenticated"""
        return session.get('admin_authenticated', False)

    def require_auth(self, f):
        """Decorator to require authentication for routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                if request.is_json:
                    return jsonify({"error": "Authentication required"}), 401
                else:
                    return redirect('/admin/login')
            return f(*args, **kwargs)
        return decorated_function


# Global auth instance
auth = SimpleAuth()


def require_admin_auth(f):
    """Decorator function for requiring admin authentication"""
    return auth.require_auth(f)