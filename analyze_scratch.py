import json, sys
from collections import defaultdict

TRIGGER_OPCODES = [
    'event_whenflagclicked', 'event_whenbroadcastreceived',
    'event_whenkeypressed', 'control_start_as_clone', 'procedures_definition'
]

def load_project(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_duplicates(targets):
    issues = []
    for t in targets:
        if t.get('isStage'): continue
        name = t.get('name','Unknown')
        blocks = t.get('blocks',{})
        tops = [b for b in blocks.values() if b.get('topLevel',False)]
        ops = defaultdict(int)
        for b in tops: ops[b.get('opcode')] += 1
        dups = [op for op,c in ops.items() if c > 1]
        if dups: issues.append(f'Sprite "{name}" has duplicate top-level scripts')
    return issues

def check_dead_code(targets):
    issues = []
    for t in targets:
        if t.get('isStage'): continue
        name = t.get('name','Unknown')
        tops = [b for b in t.get('blocks',{}).values() if b.get('topLevel',False)]
        dead = [b for b in tops if b.get('opcode') not in TRIGGER_OPCODES]
        if dead: issues.append(f'Sprite "{name}" has {len(dead)} block(s) with no trigger (dead code)')
    return issues

def check_naming(targets):
    DEFAULT = ['Sprite1','Sprite2','Sprite3','Sprite4','Cat','Sprite']
    return [f'Default name: "{t["name"]}"'
            for t in targets if not t.get('isStage') and t.get('name') in DEFAULT]

def run_analysis(fp):
    project = load_project(fp)
    targets = project.get('targets',[])
    issues = check_duplicates(targets) + check_dead_code(targets) + check_naming(targets)
    print(f'\nAnalyzing: {fp}')
    print(f'Issues found: {len(issues)}')
    for i in issues: print(f'  - {i}')
    if not issues: print('  No bad habits detected. LLM may be needed.')
    return issues

if __name__ == '__main__':
    run_analysis(sys.argv[1] if len(sys.argv) > 1 else 'project.json')
