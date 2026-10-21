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
    from .kernels import KERNELS
except ImportError:
    from kernels import KERNELS

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'sections_4&5_Tradingview'
OUT=ROOT/'Section_4_Features/individual'
REVIEWED_SHA256='53788214fddf98ae8d5bd2cdb50bb9c413e7689f9c0a4b28221c46ad1a97dde5'
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

# Feature boundaries are source-line spans, not renamed broad Python categories.
SPANS=[('price',793,806),('ema',807,823),('ema_structure',824,872),('wma',873,878),('vwap',879,959),
 ('ema_position',960,971),('rsi',972,976),('dmi',977,978),('adx',979,979),('di_metrics',980,984),('momentum_weakening',985,987),('momentum_divergence',988,993),('atr',994,1003),('volume',1004,1012),
 ('zone_geometry',1013,1215),('support_zones',1216,1631),('institutional_support',1632,1990),('resistance_zones',1991,2406),('institutional_resistance',2407,2762),
 ('swing_pivots',2763,2908),('structure',2909,3252),('break_of_structure',3253,3451),('fair_value_gaps',3452,3877),('candle',3878,3895),('fractal_pivots',3896,3900),('engulfing',3910,3923),('rejection',3924,3934),('break_retest',3935,3948),('price_change',3949,3954),
 ('fibonacci',3955,4099),('liquidity_pools',4100,4146),('liquidity_sweeps',4147,4162),('absorption',4163,4199),('liquidity_type',4200,4208),('external_liquidity',4209,4237),('internal_liquidity',4238,4245),('liquidity_clusters',4246,4267),('liquidity_age',4268,4283),('liquidity_importance',4284,4332),('nearest_liquidity',4333,4365),('order_blocks',4366,4610),('breaker_blocks',4611,4736),
 ('volume_profile',4737,4901),('range',4902,4914),('swing_levels',4915,4922),('session_clock',4923,4962),('asia_session',4963,4984),('london_session',4985,5006),('newyork_session',5007,5028),('nearest_session_levels',5037,5098),('ema_extension',5099,5104),('daily_levels',5105,5112)]


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
    modules=[];manifest=[];generated={}
    # Persistent memory declared outside the market function belongs to each pair.
    globals_=statements(lines,609,780)
    globals_=[(indent+4,text,line) for indent,text,line in globals_]
    for name,start,end in SPANS:
        items=statements(lines,start,end)
        extras={'candle':list(range(3901,3909)),'asia_session':[5030,5033],'london_session':[5031,5034],'newyork_session':[5032,5035]}.get(name,[])
        for extra in extras:items+=statements(lines,extra,extra)
        if name=='price':
            code='"""Persistent zone arrays/constants, scoped by pair, never global across markets."""\nfrom . import runtime as rt\n\ndef update(e):\n'+translate(globals_)+'\n'
            generated[OUT/'_memory.py']=code
        # Fix the source's boundary stall, retaining its larger-neighbor selection.
        items=[(indent,'if vaLowIndex > 0 and (vaHighIndex == vpBins - 1 or leftVol >= rightVol)' if line==4816 else text,line) for indent,text,line in items]
        FEATURE_WRITES.clear()
        code='"""'+name.replace('_',' ').title()+f'. Pine source lines {start}–{end}. Generated by conversion/compile_reference.py.\nDo not edit generated formulas; review source corrections in the converter."""\nfrom . import runtime as rt\n\ndef update(e):\n'+translate(items)+'\n'
        code+=KERNELS.get(name,'')
        ast.parse(code);generated[OUT/(name+'.py')]=code;modules.append(name);manifest.append({'feature':name,'start':start,'end':end,'extra_lines':extras,'outputs':sorted(FEATURE_WRITES)})
    # Regime outputs each have their own feature module.
    for name,start,end in [('control',5741,5760),('energy',5761,5778),('regime',5779,5819),('fatigue',5820,5833),('trend_state',5834,5870),('transition',5871,5893)]:
        items=statements(lines,start,end)
        FEATURE_WRITES.clear()
        code=f'"""Section 5: {name}; Pine lines {start}–{end}."""\nfrom Section_4_Features.individual import runtime as rt\n\ndef update(e):\n'+translate(items)+'\n'
        target=ROOT/'Section_5_Market_Regime/features'
        target.mkdir(exist_ok=True)
        generated[target/'__init__.py']='"""Individual Section 5 regime features."""\n'
        ast.parse(code);generated[target/(name+'.py')]=code
        modules.append('Section_5_Market_Regime.features.'+name)
        manifest.append({'feature':name,'section':5,'start':start,'end':end,'outputs':sorted(FEATURE_WRITES)})
    contracts=[]
    for line in lines[23:608]:
        m=re.fullmatch(r'\s+(float|int|bool|string) (\w+)\s*',line)
        if m:contracts.append((m[2],m[1]))
    metadata={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'modules':modules,'manifest':manifest,'history':sorted(HISTORY),'reads':sorted(READS),'writes':sorted(WRITES),'calls':sorted(CALLS),'types':TYPES,'contract':contracts,'persistent':sorted(PERSIST)}
    generated[OUT/'__init__.py']='"""Individual, ordered feature calculations translated from the Pine reference."""\n'
    generated[OUT/'manifest.json']=json.dumps(metadata,indent=2)+'\n'
    for path,code in generated.items():path.write_text(code)
    print(f'Generated {len(modules)} feature modules. External names: '+', '.join(sorted(READS-WRITES)))

if __name__=='__main__':main()
