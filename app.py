from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import zipfile
import tempfile
from collections import Counter

app = Flask(__name__)
CORS(app)

TRIGGER_OPCODES = [
    'event_whenflagclicked', 'event_whenbroadcastreceived',
    'event_whenkeypressed', 'control_start_as_clone', 'procedures_definition'
]

current_project = {}
tokens_remaining = 3
conversation_history = []
current_low_dims = []


def build_project_summary(targets, scores):
    sprites = [t for t in targets if not t.get('isStage')]
    sprite_names = [t.get('name', 'Unknown') for t in sprites]
    vars_total = sum(len(t.get('variables', {})) for t in targets)
    custom_count = 0

    for t in targets:
        for b in t.get('blocks', {}).values():
            if b.get('opcode') == 'procedures_definition':
                custom_count += 1

    summary = f"This Scratch project has {len(sprites)} sprites: {', '.join(sprite_names)}. "
    summary += f"It uses {vars_total} variables and {custom_count} custom blocks."
    return summary


def get_scores(json_project):
    from hairball3.mastery import Mastery
    mastery = Mastery(filename='project', json_project=json_project)
    raw = mastery.get_scores()
    return {
        'Logic':               raw.get('Logic', 0),
        'Abstraction':         raw.get('Abstraction', 0),
        'Data Representation': raw.get('DataRepresentation', 0),
        'Math Operators':      raw.get('MathOperators', 0),
        'Flow Control':        raw.get('FlowControl', 0),
        'Synchronization':     raw.get('Synchronization', 0),
        'Parallelism':         raw.get('Parallelization', 0),
        'User Interactivity':  raw.get('UserInteractivity', 0),
        'Motion Operators':    raw.get('MotionOperators', 0),
    }



def check_bad_habits(targets):
    issues = []

    for t in targets:
        if t.get('isStage'):
            continue
        name = t.get('name', 'Unknown')
        blocks = t.get('blocks', {})
        tops = [b for b in blocks.values() if b.get('topLevel', False)]

        keys = []
        for b in tops:
            opcode = b.get('opcode', '')
            if opcode == 'event_whenbroadcastreceived':
                msg = b.get('fields', {}).get('BROADCAST_OPTION', ['unknown'])[0]
                keys.append(f'{opcode}:{msg}')
            else:
                keys.append(opcode)

        dupes = {k: c for k, c in Counter(keys).items() if c > 1}
        for key, count in dupes.items():
            label = key.split(':')[1] if ':' in key else key
            issues.append(f'Sprite "{name}" has {count} scripts triggered by "{label}"')

    for t in targets:
        if t.get('isStage'):
            continue
        name = t.get('name', 'Unknown')
        tops = [b for b in t.get('blocks', {}).values() if b.get('topLevel', False)]
        dead = [b for b in tops if b.get('opcode') not in TRIGGER_OPCODES]
        if dead:
            issues.append(f'Sprite "{name}" has {len(dead)} block(s) with no trigger')

    # same default names as Dr. Scratch
    DEFAULT = ['Sprite', 'Objeto', 'Personatge', 'Figura', 'o actor', 'Personaia']
    for t in targets:
        if not t.get('isStage') and t.get('name') in DEFAULT:
            issues.append(f'Default name: "{t["name"]}"')

    return issues


@app.route('/')
def home():
    return jsonify({'status': 'CT-Buddy Running'})


@app.route('/upload', methods=['POST'])
def upload():
    global current_project, tokens_remaining, conversation_history, current_low_dims
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'No file'}), 400

        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)

        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                project_json_content = zip_ref.read('project.json').decode('utf-8')
        except Exception:
            with open(file_path, 'r') as f:
                project_json_content = f.read()

        current_project = json.loads(project_json_content)
        tokens_remaining = 3
        conversation_history = []
        current_low_dims = []

        return jsonify({'status': 'Uploaded'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyze', methods=['GET'])
def analyze():
    global current_project, current_low_dims
    try:
        if not current_project:
            return jsonify({'error': 'No project loaded'}), 400

        targets = current_project.get('targets', [])
        issues = check_bad_habits(targets)
        scores = get_scores(current_project)

        LLM_DIMS = {'Logic', 'Abstraction', 'Data Representation', 'Math Operators'}

        ct_scores = {d: v for d, v in scores.items() if d in LLM_DIMS}
        min_score = min(ct_scores.values()) if ct_scores else 4
        low_dims = [d for d, v in ct_scores.items() if v == min_score and v < 4]
        current_low_dims = low_dims

        unlock_llm = len(issues) == 0 and len(low_dims) > 0

        return jsonify({
            'bad_habits_found': len(issues) > 0,
            'bad_habits_issues': issues,
            'dr_scratch_scores': scores,
            'unlock_llm': unlock_llm,
            'low_dims': low_dims
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/start', methods=['GET'])
def start():
    try:
        if not current_project:
            return jsonify({'error': 'No project loaded'}), 400
        targets = current_project.get('targets', [])
        scores = get_scores(current_project)
        low_dims = current_low_dims or ['Logic']
        dims_text = ', '.join(f'{d} ({scores.get(d, 0)}/4)' for d in low_dims)
        summary = (
            f"{build_project_summary(targets, scores)}\n"
            f"Low-scoring dimensions: {dims_text}.\n"
            f"The student just uploaded their project. Ask your opening Socratic question based on this specific project."
        )
        from socratic_turn1 import run as ask
        response = ask(summary, low_dims, scores)
        return jsonify({'ai_response': response, 'tokens_remaining': tokens_remaining}), 200
    except Exception as e:
        print(f"ERROR in start: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    global current_project, tokens_remaining, conversation_history, current_low_dims
    try:
        if not current_project:
            return jsonify({'error': 'No project loaded'}), 400

        data = request.get_json()
        user_question = data.get('question', '')

        if not user_question:
            return jsonify({'error': 'No question provided'}), 400

        targets = current_project.get('targets', [])
        sprite_names = [t.get('name') for t in targets if not t.get('isStage')]
        scores = get_scores(current_project)
        low_dims = current_low_dims or ['Logic']

        dims_text = ', '.join(f'{d} ({scores.get(d, 0)}/4)' for d in low_dims)

        if user_question == '__wrap_up__' or tokens_remaining <= 0:
            try:
                from socratic_turn1 import run as socratic_response

                conv_text = "\n".join([f"{m['role']}: {m['message']}" for m in conversation_history])
                summary = (
                    f"Conversation:\n{conv_text}\n\n"
                    f"Student sprites: {sprite_names}\n"
                    f"Low-scoring dimensions: {dims_text}. "
                    f"Wrap up the conversation. Tell them specifically what blocks to add to fix each low dimension."
                )

                final_msg = socratic_response(summary, low_dims, scores, final=True)
                return jsonify({
                    'ai_response': final_msg,
                    'tokens_remaining': 0,
                    'chatbot_locked': True,
                    'is_final_summary': True
                }), 200
            except Exception as e:
                print(f"ERROR in final summary: {e}")
                return jsonify({
                    'ai_response': "You've used all 3 attempts. Revise your code based on what we discussed and upload again.",
                    'tokens_remaining': 0,
                    'chatbot_locked': True
                }), 200

        conversation_history.append({'role': 'user', 'message': user_question})
        proj_summary = build_project_summary(targets, scores)

        is_last = tokens_remaining == 1 and len(conversation_history) > 1
        if is_last:
            conv_text = "\n".join([f"{m['role']}: {m['message']}" for m in conversation_history])
            summary = (
                f"Conversation:\n{conv_text}\n\n"
                f"{proj_summary}\n"
                f"Low-scoring dimensions: {dims_text}.\n"
                f"Wrap up. Tell the student specifically what Scratch blocks to add to improve each low dimension."
            )
        else:
            summary = (
                f"{proj_summary}\n"
                f"Low-scoring dimensions: {dims_text}.\n"
                f"Student said: {user_question}"
            )

        try:
            from socratic_turn1 import run as socratic_response
            ai_response = socratic_response(summary, low_dims, scores, final=is_last)
        except Exception as e:
            print(f"ERROR calling Gemini: {e}")
            ai_response = "Thinking about your answer... Consider: what blocks in Scratch let you check if something is true?"

        conversation_history.append({'role': 'ai', 'message': ai_response})
        tokens_remaining -= 1

        return jsonify({
            'ai_response': ai_response,
            'tokens_remaining': tokens_remaining,
            'chatbot_locked': tokens_remaining <= 0
        }), 200
    except Exception as e:
        print(f"ERROR in chat: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
