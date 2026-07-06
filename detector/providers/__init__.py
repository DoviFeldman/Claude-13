"""Provider registry - each source is a module with fetch(cfg) -> [Strike].

Toggle sources with ENABLE_XWEATHER / ENABLE_GLM / ENABLE_BLITZORTUNG env
vars so you can compare how each network reports the same storm.
"""

from . import xweather, goes_glm, blitzortung


def enabled_providers(cfg):
    """Return [(name, fetch_fn)] for every source toggled on."""
    providers = []
    if cfg.enable_xweather:
        providers.append(("xweather", xweather.fetch))
    if cfg.enable_glm:
        providers.append(("glm", goes_glm.fetch))
    if cfg.enable_blitzortung:
        providers.append(("blitzortung", blitzortung.fetch))
    return providers
