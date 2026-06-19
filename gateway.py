from analyze_scratch import run_analysis

LLM_DIMS = ['logic', 'abstraction', 'data representation', 'math operators']

def needs_llm(issues, scores):
    simple = [i for i in issues if any(k in i.lower() for k in ['duplicate','dead code','default'])]
    
    if simple:
        print('GATEWAY: Simple bad habits found. Static tips generated:')
        for s in simple: 
            print(f'  Tip: {s}')
    else:
        print('GATEWAY: No basic code structure issues found.')

    low = [d for d,v in scores.items() if d.lower() in LLM_DIMS and v == 0]
    
    if low:
        print(f'\nGATEWAY: Concept gap detected. LLM required for Socratic scaffolding on: {low}')
        return True
        
    print('\nGATEWAY: Computational Thinking scores are sufficient. No LLM needed.')
    return False

if __name__ == '__main__':
    import sys
    import json
    import subprocess
    
    filename = sys.argv[1] if len(sys.argv) > 1 else 'project4.json'
    issues = run_analysis(filename)

    scores = {
        'Abstraction': 1, 
        'Parallelism': 4, 
        'Logic': 0,              
        'Synchronization': 3, 
        'Flow Control': 4,
        'User Interactivity': 1, 
        'Data Representation': 1,
        'Math Operators': 0,       
        'Motion Operators': 3
    }
    
    summary = f"Scratch project file: {filename}. A creative project featuring an animated Wizard, a Dinosaur, a Boat, and Water elements."
    
    low_dims = [d for d,v in scores.items() if d.lower() in LLM_DIMS and v == 0]
    
    if needs_llm(issues, scores):
        payload = {
            "summary": summary,
            "low_dims": low_dims,
            "scores": scores
        }
        subprocess.run(['python3', 'socratic_turn1.py', json.dumps(payload)])