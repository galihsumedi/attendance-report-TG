"""
Syncs the full employee list back to nama_karyawan.py on GitHub so that
the employee database survives a Render free-tier restart.

Requires env vars GITHUB_TOKEN and GITHUB_REPO. Silently skips if either
is absent (local dev / no token configured).
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.request
import urllib.error


def _build_file_content(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        '''SELECT a.alias, e.nama_lengkap
           FROM employee_aliases a
           JOIN employees e ON e.id = a.employee_id
           ORDER BY e.nama_lengkap, a.alias'''
    ).fetchall()

    lines = ['NAMA_LENGKAP = {\n']
    for r in rows:
        lines.append(f'    {repr(r[0])}: {repr(r[1])},\n')
    lines.append('}\n')
    return ''.join(lines)


def sync_nama_karyawan(conn: sqlite3.Connection) -> None:
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    branch = os.environ.get('GITHUB_BRANCH', 'v3.0')
    if not token or not repo:
        return

    api_url = f'https://api.github.com/repos/{repo}/contents/nama_karyawan.py?ref={branch}'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
    }

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        sha = data['sha']
    except urllib.error.URLError:
        return

    new_content = _build_file_content(conn)
    payload = json.dumps({
        'message': 'sync: update nama_karyawan.py from employee DB',
        'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
        'sha': sha,
        'branch': branch,
    }).encode('utf-8')

    try:
        put_url = f'https://api.github.com/repos/{repo}/contents/nama_karyawan.py'
        req = urllib.request.Request(put_url, data=payload, headers=headers, method='PUT')
        urllib.request.urlopen(req)
    except urllib.error.URLError:
        pass
