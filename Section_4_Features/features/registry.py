"""Registry of the numbered Section 4 calculation files."""
import importlib
from Section_4_Features.execution.context import MANIFEST
from Section_4_Features.execution.contract import FIELDS,snake

MODULES=tuple(name for name in MANIFEST['modules'] if '.' not in name)


def load():
    result=[]
    for name in MANIFEST['modules']:
        if '.' in name:continue
        module=importlib.import_module('Section_4_Features.features.'+name)
        result.append({'name':name,'inputs':('context',),'module':module,
                       'output_fields':tuple(snake(field) for field in sorted({field for entry in MANIFEST['manifest'] if entry['feature']==name for field in entry['outputs']}) if snake(field) in FIELDS)})
    from .momentum_anchors import EXPORTS
    for row in result:
        if row['name']=='momentum':row['output_fields']+=tuple(EXPORTS)
    from .shared_measurements import GROUPS
    for row in result:
        row['output_fields']+=GROUPS.get(row['name'],())
    result.append({'name':'shared_measurements','inputs':('context',),
        'module':importlib.import_module('Section_4_Features.features.shared_measurements'),
        'output_fields':GROUPS['shared_measurements']})
    return result
