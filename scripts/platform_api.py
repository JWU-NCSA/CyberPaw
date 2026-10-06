"""Everything the CyberPaw scripts use from the underlying CTF platform, in one place.

apply_config.py and seed_demo.py import from here, so the platform's package name appears only in
this file. The shell wrappers copy it into the container next to the script they run.
"""
from CTFd import create_app  # noqa: F401
from CTFd.cache import clear_challenges, clear_config, clear_pages, clear_standings  # noqa: F401
from CTFd.models import (  # noqa: F401
    ChallengeFiles, Challenges, Configs, Fails, Flags, Hints, Pages, Solves, Tags, Users, db,
)
from CTFd.plugins.cyberpaw import CyberpawChallengeMeta  # noqa: F401
from CTFd.plugins.cyberpaw.first_paw import sync_awards as sync_first_paw_awards  # noqa: F401
from CTFd.plugins.dynamic_challenges import DynamicChallenge, DynamicValueChallenge  # noqa: F401
from CTFd.utils import set_config  # noqa: F401
from CTFd.utils.uploads import delete_file, upload_file  # noqa: F401
