"""
Dropbox utilities for AI DJ.
Uses refresh token auth (set in ~/.dropbox_refresh_token and ~/.dropbox_app_creds).
"""

import json
import os
from pathlib import Path

DROPBOX_TOKEN_FILE = Path.home() / '.dropbox_token'
DROPBOX_REFRESH_FILE = Path.home() / '.dropbox_refresh_token'
DROPBOX_CREDS_FILE = Path.home() / '.dropbox_app_creds'


def _get_dbx():
    """Get authenticated Dropbox client using refresh token flow."""
    import dropbox

    # Try refresh token first
    refresh_token = None
    app_key = None
    app_secret = None

    if DROPBOX_REFRESH_FILE.exists():
        refresh_token = DROPBOX_REFRESH_FILE.read_text().strip()

    if DROPBOX_CREDS_FILE.exists():
        creds = json.loads(DROPBOX_CREDS_FILE.read_text())
        app_key = creds.get('app_key')
        app_secret = creds.get('app_secret')

    if refresh_token and app_key:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret or None,
        )
        return dbx

    # Fallback: short-lived token
    if DROPBOX_TOKEN_FILE.exists():
        token = DROPBOX_TOKEN_FILE.read_text().strip()
        return dropbox.Dropbox(token)

    raise RuntimeError("No Dropbox auth found. Need ~/.dropbox_refresh_token + ~/.dropbox_app_creds or ~/.dropbox_token")


def list_files(path='/ai-dj/files/'):
    """List all files in a Dropbox folder. Returns list of dicts with name, path_display."""
    dbx = _get_dbx()
    try:
        result = dbx.files_list_folder(path)
        entries = []
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                entries.append({
                    'name': entry.name,
                    'path_display': entry.path_display,
                    'size': entry.size,
                })
        # Handle pagination
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    entries.append({
                        'name': entry.name,
                        'path_display': entry.path_display,
                        'size': entry.size,
                    })
        return entries
    except Exception as e:
        raise RuntimeError(f"Dropbox list failed: {e}")


def download_file(dropbox_path, local_path):
    """Download a file from Dropbox to local path."""
    dbx = _get_dbx()
    dbx.files_download_to_file(local_path, dropbox_path)


def get_temporary_link(dropbox_path):
    """Get a temporary download link (4h expiry)."""
    dbx = _get_dbx()
    result = dbx.files_get_temporary_link(dropbox_path)
    return result.link
