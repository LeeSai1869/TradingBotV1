"""Reviewed, version-pinned production strategies; never load executable user input."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from .rules import di_turning_point_v3


@dataclass(frozen=True)
class Strategy:
    id: str
    version: int
    name: str
    module: object
    fingerprint: str
    alternate_signals: bool = True

    def public(self):
        return dict(strategy_id=self.id, version=self.version, name=self.name,
                    fingerprint=self.fingerprint, lookback=self.module.LOOKBACK)


# Keep this implementation file when introducing later versions. A registered
# version is immutable; changing a live rule must introduce a new version entry.
DEFINITIONS = {
    ('di_turning_point', 3): Strategy('di_turning_point', 3, 'DI turning point · v3',
        di_turning_point_v3, '54fef5dbd5d005899dd3fdd2551cb3732cd344ab65f3e6ff1742b46dc6614163'),
}


def require(strategy_id, version):
    if type(version) is not int or (strategy_id, version) not in DEFINITIONS:
        raise ValueError('Choose a registered production strategy/version')
    definition=DEFINITIONS[strategy_id, version]
    if type(definition.module.LOOKBACK) is not int or not 0<=definition.module.LOOKBACK<=1000:
        raise ValueError('Strategy lookback must be bounded to 0..1000 candles')
    path=getattr(definition.module,'__file__',None)
    if path and hashlib.sha256(Path(path).read_bytes()).hexdigest()!=definition.fingerprint:
        raise ValueError('Registered strategy source changed; add a new immutable version')
    return definition


def catalog():
    return [value.public() for value in DEFINITIONS.values()]
