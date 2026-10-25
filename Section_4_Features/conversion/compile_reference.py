"""Build reviewable, feature-specific Python from the checked-in Pine reference.

Build-time only: the application never evaluates Pine or arbitrary Python text.
Unsupported syntax and missing dependencies fail the conversion explicitly.
"""
from pathlib import Path
import re
import json
import ast
import hashlib
try:
    from .kernels import KERNELS, VOLUME_PROFILE_HISTOGRAM
except ImportError:
    from kernels import KERNELS, VOLUME_PROFILE_HISTOGRAM

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'sections_4&5_Tradingview'
OUT=ROOT/'Section_4_Features/features'
SUPPORT=ROOT/'Section_4_Features/execution'
REVIEWED_SHA256='acc6073b0be22e1cd7eda992fe64c01612c56d3879d8a909adb48c487a43e402'
TOKEN=re.compile(r'\s*("(?:\\.|[^"\\])*"|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|==|!=|>=|<=|:=|\+=|-=|\*=|/=|[+*/%<>=?:.,()\[\]-])')
HISTORY=set();READS=set();WRITES=set();FEATURE_WRITES=set();CALLS=set();TYPES={};PERSIST=set()

class Expr:
    def __init__(self,text,line):
        self.t=[];pos=0;self.line=line
        while pos<len(text):
            match=TOKEN.match(text,pos)
            if not match:raise ValueError(f'Pine line {line}: token near {text[pos:]}')
            self.t.append(match.group(1));pos=match.end()
        self.i=0
    def peek(self):return self.t[self.i] if self.i<len(self.t) else ''
    def pop(self,value=None):
        token=self.peek()
        if value is not None and token!=value:raise ValueError(f'Line {self.line}: wanted {value}, got {token}')
        self.i+=1;return token
    def parse(self,minimum=0):
        token=self.pop()
        if token in ('-','+','not'):
            value=self.parse(30)
            node=('not',value) if token=='not' else ('neg',value) if token=='-' else value
        elif token=='(':
            node=self.parse();self.pop(')')
        elif token.startswith('"'):node=('literal',ast.literal_eval(token))
        elif re.match(r'^\d',token):node=('literal',float(token) if any(c in token for c in '.eE') else int(token))
        elif re.fullmatch(r'[A-Za-z_]\w*',token):node=('name',token)
        else:raise ValueError(f'Line {self.line}: unexpected expression {token}')
        while True:
            token=self.peek()
            if token=='.':
                self.pop();node=('attr',node,self.pop());continue
            if token=='(':
                self.pop();args=[];kwargs=[]
                while self.peek()!=')':
                    if self.i+1<len(self.t) and self.t[self.i+1]=='=':
                        key=self.pop();self.pop('=');kwargs.append((key,self.parse()))
                    else:args.append(self.parse())
                    if self.peek()!=',':break
                    self.pop(',')
                self.pop(')');node=('call',node,args,kwargs);continue
            if token=='[':
                self.pop();index=self.parse();self.pop(']');node=('history',node,index);continue
            precedence={'or':2,'and':3,'==':5,'!=':5,'>':5,'<':5,'>=':5,'<=':5,'+':10,'-':10,'*':20,'/':20,'%':20}.get(token,-1)
            if precedence<minimum:break
            self.pop();right=self.parse(precedence+1);node=('op',token,node,right)
        if minimum==0 and self.peek()=='?':
            self.pop();yes=self.parse();self.pop(':');no=self.parse();node=('ternary',node,yes,no)
        return node
    def compile(self):
        node=self.parse()
        if self.peek():raise ValueError(f'Line {self.line}: trailing tokens {self.t[self.i:]}')
        return emit(node,self.line)

def dotted(node):
    if node[0]=='name':return node[1]
    if node[0]=='attr':return dotted(node[1])+'.'+node[2]
    raise ValueError(node)

def emit(n,line):
    kind=n[0]
    if kind=='literal':return repr(n[1])
    if kind=='name':
        name=n[1]
        if name in ('true','false','na'):return {'true':'True','false':'False','na':'rt.NA'}[name]
        READS.add(name);return f'e[{name!r}]'
    if kind=='attr':
        name=dotted(n)
        if name.startswith('f.'):name=name[2:]
        elif name=='marketMemory.lastRegime':name='lastRegime'
        READS.add(name);return f'e[{name!r}]'
    if kind=='history':
        name=dotted(n[1]);HISTORY.add(name);READS.add(name)
        return f'e.previous({name!r}, {emit(n[2],line)})'
    if kind=='neg':return f'rt.neg({emit(n[1],line)})'
    if kind=='not':return f'(not rt.truth({emit(n[1],line)}))'
    if kind=='ternary':return f'({emit(n[2],line)} if rt.truth({emit(n[1],line)}) else {emit(n[3],line)})'
    if kind=='op':
        op,a,b=n[1],emit(n[2],line),emit(n[3],line)
        if op in ('and','or'):return f'(rt.truth({a}) {op} rt.truth({b}))'
        return f'rt.binary({op!r}, {a}, {b})'
    if kind=='call':
        name=dotted(n[1]);CALLS.add(name)
        args=[emit(arg,line) for arg in n[2]]
        if name.startswith('ta.'):
            return f'e.ta({name[3:]!r}, {str(line)!r}, '+', '.join(args)+')'
        if name=='request.security':return f'e.daily({dotted(n[2][2])!r})'
        if name=='time':return f'e.session({args[1]})'
        if name=='timeframe.change':return 'e.new_day'
        if name.startswith('input.'):return f'e.input({args[1]}, {args[0]})'
        if name=='normalizeRelative':return 'rt.normalize('+', '.join(args)+')'
        if name in ('int','float','na'):return f'rt.{dict(int="to_int",float="to_float",na="is_na")[name]}('+', '.join(args)+')'
        if '.' in name and name.split('.')[-1] in ('get','set','size','push','remove','clear','indexof','max','min') and not name.startswith(('array.','math.')):
            base,method=name.rsplit('.',1);READS.add(base);return 'rt.arr_'+method+'(e['+repr(base)+']'+(', '+', '.join(args) if args else '')+')'
        if name.startswith('array.'):
            method=name[6:];method={'from':'from_values'}.get(method,method)
            return 'rt.arr_'+method+'('+', '.join(args)+')'
        if name.startswith('math.'):return 'rt.math_'+name[5:]+'('+', '.join(args)+')'
        if name.startswith('str.'):return 'rt.str_'+name[4:]+'('+', '.join(args)+')'
        raise ValueError(f'Line {line}: unsupported call {name}')
    raise ValueError(n)

# File boundaries follow the numbered 4.2 calculation sections, not inferred topics.
SECTIONS = {
    '4.2.1': 'price', '4.2.2': 'trend', '4.2.3': 'ema_structure',
    '4.2.4': 'vwap', '4.2.5': 'price_location', '4.2.6': 'momentum',
    '4.2.7': 'volatility', '4.2.8': 'volume', '4.2.9': 'support_resistance',
    '4.2.10': 'market_structure', '4.2.11': 'fair_value_gaps',
    '4.2.12': 'candle', '4.2.13': 'price_change', '4.2.14': 'fibonacci',
    '4.2.16': 'liquidity', '4.2.17': 'order_blocks', '4.2.18': 'volume_profile',
    '4.2.19': 'range', '4.2.20': 'swing_location', '4.2.21': 'sessions',
    '4.2.22': 'price_extension', '4.2.23': 'daily_levels',
}

def section_spans(lines):
    headers=[]
    for number,line in enumerate(lines,1):
        match=re.match(r'\s*//\s+(4\.2\.\d+)\s+(.+)',line)
        if match:
            section=match[1]
            if section not in SECTIONS:raise ValueError(f'Unreviewed calculation section: {section}')
            headers.append((section,SECTIONS[section],number,match[2].strip()))
    if [x[0] for x in headers]!=list(SECTIONS):raise ValueError('Numbered source sections changed')
    return [(section,name,start,headers[i+1][2]-1 if i+1<len(headers) else 5112,title)
            for i,(section,name,start,title) in enumerate(headers)]


def section_kernels(name):
    if name=='trend':
        return KERNELS['ema'].replace('def calculate(', 'def calculate_ema(')
    if name=='ema_structure':
        return KERNELS['wma'].replace('def calculate(', 'def calculate_wma(')
    if name=='momentum':
        return (KERNELS['rsi'].replace('def calculate(', 'def calculate_rsi(')+
                KERNELS['dmi'].replace('def calculate(', 'def calculate_dmi(')+
                KERNELS['adx'].replace('def calculate(', 'def calculate_adx('))
    return KERNELS.get('atr' if name=='volatility' else name,'')


def statements(lines,start,end):
    items=[];pending='';pending_line=None;balance=0;ternary=0
    for index in range(start-1,end):
        raw=lines[index];text=raw.split('//')[0].rstrip()
        if not text.strip():continue
        indent=len(text)-len(text.lstrip());text=text.strip()
        if not pending:pending_line=index+1;pending_indent=indent
        pending+=' '+text
        # All quoted strings are removed before counting continuation punctuation.
        stripped=re.sub(r'"(?:\\.|[^"\\])*"','',text)
        balance+=stripped.count('(')+stripped.count('[')-stripped.count(')')-stripped.count(']')
        ternary+=stripped.count('?')-stripped.count(':')+stripped.count(':=')
        if balance or re.search(r'(?:[=?:,+*/-]|\b(?:and|or))\s*$',pending):continue
        items.append((pending_indent,pending.strip(),pending_line));pending='';balance=0;ternary=0
    if pending:raise ValueError(f'Unclosed statement at {pending_line}: {pending}')
    return items


def translate(items):
    result=[]
    for indent,text,line in items:
        level=max(0,(indent-4)//4);prefix='    '*(level+1)
        if text.startswith('if '):code='if rt.truth('+Expr(text[3:],line).compile()+'):'
        elif text.startswith('else if '):code='elif rt.truth('+Expr(text[8:],line).compile()+'):'
        elif text=='else':code='else:'
        elif text.startswith('while '):code='while rt.truth('+Expr(text[6:],line).compile()+'):'
        elif text.startswith('for '):
            m=re.fullmatch(r'for (\w+) = (.+) to (.+)',text)
            if not m:raise ValueError((line,text))
            WRITES.add(m[1]);code=f'for e[{m[1]!r}] in rt.inclusive({Expr(m[2],line).compile()}, {Expr(m[3],line).compile()}):'
        elif text in ('break','continue'):code=text
        else:
            # Declarations, tuple declarations, reassignment and expression statements.
            m=re.match(r'(?:(var|const)\s+)?(?:(float|int|bool|string|MTFData)(?:\[\])?\s+)?(\w+|\[[\w, ]+\])\s*(:=|\+=|-=|\*=|/=|=)\s*(.*)$',text)
            if not m:code=Expr(text,line).compile()
            else:
                persistence,type_,name,op,rhs=m.groups();names=[x.strip() for x in name.strip('[]').split(',')]
                WRITES.update(names);FEATURE_WRITES.update(names)
                if type_:
                    for n in names:TYPES[n]=type_
                expression=Expr(rhs,line).compile()
                target=', '.join(f'e[{n!r}]' for n in names)
                if op in ('+=','-=','*=','/='):expression=f'rt.binary({op[0]!r}, {target}, {expression})'
                if persistence in ('var','const'):
                    if len(names)!=1:raise ValueError((line,text))
                    PERSIST.add(name);code=f'if {name!r} not in e.persistent:\n{prefix}    e.initialize({name!r}, {expression})'
                else:code=f'{target} = {expression}'
        result.append(prefix+f'# Pine {line}\n'+prefix+code)
    return '\n'.join(result)


def main():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=REVIEWED_SHA256:
        raise ValueError('Reference changed: review feature boundaries and contract bindings before regenerating')
    lines=SOURCE.read_text().splitlines();OUT.mkdir(exist_ok=True)
    modules=[];manifest=[];generated={};steps=[]
    SUPPORT.mkdir(exist_ok=True)
    globals_=statements(lines,609,780)
    globals_=[(indent+4,text,line) for indent,text,line in globals_]
    code='\"\"\"Per-pair persistent arrays and constants from Pine 4.1.22.\"\"\"\nfrom . import runtime as rt\n\ndef update(e):\n'+translate(globals_)+'\n'
    ast.parse(code);generated[SUPPORT/'memory.py']=code
    for section,name,start,end,title in section_spans(lines):
        items=statements(lines,start,end)
        # Reviewed correction: keep expansion inside the actual volume-profile bins.
        items=[(indent,'if vaLowIndex > 0 and (vaHighIndex == vpBins - 1 or leftVol >= rightVol)' if line==4816 else text,line) for indent,text,line in items]
        FEATURE_WRITES.clear()
        code=f'\"\"\"{section} {title}. Pine lines {start}–{end}.\nGenerated by conversion/compile_reference.py; one numbered section per file.\"\"\"\nfrom ..execution import runtime as rt\n\ndef update(e):\n'+translate(items)+'\n'+section_kernels(name)
        if name=='volume_profile':
            begin=code.index('        # Pine 4775')
            finish=code.index('        # Pine 4790',begin)
            code=code[:begin]+'        # Pine 4775–4788: native histogram, identical ordered additions.\n        accumulate_histogram(e)\n'+code[finish:]+VOLUME_PROFILE_HISTOGRAM
        ast.parse(code);generated[OUT/(name+'.py')]=code;modules.append(name)
        steps.append({'module':name,'function':'update'})
        manifest.append({'feature':name,'section':section,'title':title,'start':start,'end':end,'outputs':sorted(FEATURE_WRITES)})
    # Regime outputs each have their own feature module.
    for name,start,end in [('control',5741,5760),('energy',5761,5778),('regime',5779,5819),('fatigue',5820,5833),('trend_state',5834,5870),('transition',5871,5893)]:
        items=statements(lines,start,end)
        FEATURE_WRITES.clear()
        code=f'"""Section 5: {name}; Pine lines {start}–{end}."""\nfrom Section_4_Features.execution import runtime as rt\n\ndef update(e):\n'+translate(items)+'\n'
        target=ROOT/'Section_5_Market_Regime/features'
        target.mkdir(exist_ok=True)
        generated[target/'__init__.py']='"""Individual Section 5 regime features."""\n'
        ast.parse(code);generated[target/(name+'.py')]=code
        modules.append('Section_5_Market_Regime.features.'+name)
        steps.append({'module':'Section_5_Market_Regime.features.'+name,'function':'update'})
        manifest.append({'feature':name,'section':5,'start':start,'end':end,'outputs':sorted(FEATURE_WRITES)})
    contracts=[]
    for line in lines[23:608]:
        m=re.fullmatch(r'\s+(float|int|bool|string) (\w+)\s*',line)
        if m:contracts.append((m[2],m[1]))
    metadata={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'modules':modules,'steps':steps,'manifest':manifest,'history':sorted(HISTORY),'reads':sorted(READS),'writes':sorted(WRITES),'calls':sorted(CALLS),'types':TYPES,'contract':contracts,'persistent':sorted(PERSIST)}
    generated[OUT/'__init__.py']='"""Numbered Section 4 calculations translated from the Pine reference."""\n'
    generated[ROOT/'Section_4_Features/conversion/manifest.json']=json.dumps(metadata,indent=2)+'\n'
    for path,code in generated.items():path.write_text(code)
    print(f'Generated {len(modules)} feature modules. External names: '+', '.join(sorted(READS-WRITES)))

if __name__=='__main__':main()
