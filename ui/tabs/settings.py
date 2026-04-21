"""
ui/tabs/settings.py — SettingsTab thin wrapper
All implementation lives in MainPanel._build_settings_tab().
"""


def build(parent, panel):
    """Build and return the settings tab frame."""
    return panel._build_settings_tab(parent)
