"""Resolve explicit sandbox grants without broad host access."""
import os
from pathlib import Path

def is_flatpak():return bool(os.environ.get('FLATPAK_ID'))

def storage_paths(config=None,state=None):
    home=Path.home()
    if is_flatpak():
        # Flatpak supplies HOST_ values; only gtk-3.0/gtk-4.0 and accented
        # state beneath them are granted by the application manifest.
        config=Path(os.environ.get('HOST_XDG_CONFIG_HOME',str(home/'.config')))
        state=Path(os.environ.get('HOST_XDG_STATE_HOME',str(home/'.local/state')))
    else:
        config=Path(config or os.environ.get('XDG_CONFIG_HOME',str(home/'.config')))
        state=Path(state or os.environ.get('XDG_STATE_HOME',str(home/'.local/state')))
    if not config.is_absolute() or not state.is_absolute():raise ValueError('XDG storage locations must be absolute')
    return config,state
