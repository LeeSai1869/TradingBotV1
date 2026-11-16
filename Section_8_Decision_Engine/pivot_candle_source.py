"""Compact research storage with lazy dictionary rows for the existing analyzer."""
from collections.abc import Sequence


class PackedCandles(Sequence):
    def __init__(self, packed, columns, contexts):
        self.packed, self.columns, self.contexts = packed, columns, contexts
        self.column_index = {name: i for i, name in enumerate(columns)}

    def __len__(self):
        return len(self.packed)

    def __getitem__(self, at):
        if isinstance(at, slice):
            return [self[i] for i in range(*at.indices(len(self))) ]
        p = self.packed[at]
        row = dict(zip(('open_time', 'close_time', 'open', 'high', 'low', 'close', 'volume'), p[:7]))
        row['features'] = dict(zip(self.columns, p[7]))
        row['feature_valid'] = True
        row['context'] = {name: dict(self.contexts[index], candle_open_time=p[0], candle_close_time=p[1], as_of=p[1]+1)
                          for name, index in zip(('STRUCTURE', 'TREND', 'REGIME'), p[8])}
        return row

    def feature(self, name):
        at = self.column_index.get(name)
        return (r[7][at] if at is not None else None for r in self.packed)


def unpack(source):
    if 'packed_candles' not in source:
        return source
    result = dict(source)
    packed = result.pop('packed_candles')
    contexts = result.pop('context_table')
    result['candles'] = PackedCandles(packed, source['exported_feature_columns'], contexts)
    return result
