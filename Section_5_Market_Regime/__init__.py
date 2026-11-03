"""Section 5 public legacy exports, loaded only when requested.

Importing a pure analytical engine must not eagerly load Section 4 execution or
Core compatibility code. Existing packet names retain their original behavior.
"""
__all__=['RegimePacket','create_regime_packet']


def __getattr__(name):
    if name not in __all__:raise AttributeError(name)
    from importlib import import_module
    value=getattr(import_module('.regime_packet',__name__),name)
    globals()[name]=value
    return value
