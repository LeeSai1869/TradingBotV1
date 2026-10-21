"""Registry of individual converted features; legacy pure APIs remain importable."""
import importlib
from Section_4_Features.individual.context import MANIFEST
from Section_4_Features.individual.contract import FIELDS,snake

MODULES=tuple(name for name in MANIFEST['modules'] if '.' not in name)


def load():
    result=[]
    for name,entry in zip(MANIFEST['modules'],MANIFEST['manifest']):
        if '.' in name:continue
        module=importlib.import_module('Section_4_Features.individual.'+name)
        result.append({'name':name,'inputs':('context',),'module':module,
                       'output_fields':tuple(snake(field) for field in entry['outputs'] if snake(field) in FIELDS)})
    return result
