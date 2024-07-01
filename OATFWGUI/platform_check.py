import enum
import platform
import logging

platform_lookup_cache = None
log = logging.getLogger('')


class PlatformEnum(enum.Enum):
    LINUX = enum.auto()
    WINDOWS = enum.auto()
    MACOS = enum.auto()
    UNKNOWN = enum.auto()


def get_platform() -> PlatformEnum:
    global platform_lookup_cache
    if platform_lookup_cache is not None:
        # Not really for performance, but so that we can use the logger
        # without worrying about recursion
        return platform_lookup_cache

    # No logging just yet!!
    platform_str = platform.system().lower()
    if 'windows' in platform_str:
        platform_lookup = PlatformEnum.WINDOWS
    elif 'linux' in platform_str:
        platform_lookup = PlatformEnum.LINUX
    elif 'darwin' in platform_str:
        platform_lookup = PlatformEnum.MACOS
    else:
        platform_lookup = PlatformEnum.UNKNOWN
    platform_lookup_cache = platform_lookup  # Cache return
    # We can now use logging

    log.debug(f'platform_str={platform_str}')
    if platform_lookup == PlatformEnum.UNKNOWN:
        log.warning(f'Unknown platform {platform_str}!')

    return platform_lookup
