"""Reset transient feature caches. Permanent replay checkpoints remain intact."""

def reset_all_state():
    from . import processor
    from Section_5_Market_Regime.Market_Regime import _LAST
    processor._PREVIEWS.clear();processor._ENGINES.clear();processor._BACKUP_CHECKED.clear();_LAST.clear()
