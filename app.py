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


# builds a plain-English description of the project to give Gemini context
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


# Temporary 

## mock scores  -- will get replaced with Dr Scratch' metrics
def get_mock_scores(targets):
    sprites = [t for t in targets if not t.get('isStage')]
    num_sprites = max(len(sprites), 1)

    logic_blocks = 0
    math_blocks = 0
    custom_blocks = 0
    vars_total = sum(len(t.get('variables', {})) for t in targets)

    for t in targets:
        for b in t.get('blocks', {}).values():
            op = b.get('opcode', '')
            if any(x in op for x in ('_if', 'repeat', 'wait_until')):
                logic_blocks += 1
            if op.startswith('operator_'):
                math_blocks += 1
            if op == 'procedures_definition':
                custom_blocks += 1

    def score(val, thresholds):
        for i, t in enumerate(thresholds):
            if val < t:
                return i
        return 4

    logic_score = score(logic_blocks / num_sprites, [3, 8, 15, 25])
    abstraction_score = score(custom_blocks, [3, 6, 12, 20])
    data_score = score(vars_total / num_sprites, [2, 4, 6, 10])
    math_score = score(math_blocks, [2, 10, 30, 60])

    return {
        'Logic': logic_score,
        'Abstraction': abstraction_score,
        'Data Representation': data_score,
        'Math Operators': math_score,
        'Parallelism': 3,
        'Synchronization': 3,
        'Flow Control': 4,
        'User Interactivity': 2,
        'Motion Operators': 3,
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

    DEFAULT = ['Sprite1', 'Sprite2', 'Sprite3', 'Sprite4', 'Cat', 'Sprite']
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
        scores = get_mock_scores(targets)

        LLM_DIMS = {'logic', 'abstraction', 'data representation', 'math operators'}
        low_dims = [d for d, v in scores.items() if d.lower() in LLM_DIMS and v == 0]
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
        scores = get_mock_scores(targets)
        low_dims = current_low_dims or ['Logic']
        dims_text = ', '.join(f'{d} (0/4)' for d in low_dims)
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
        scores = get_mock_scores(targets)
        low_dims = current_low_dims or ['Logic']

        dims_text = ', '.join(f'{d} (0/4)' for d in low_dims)

        if tokens_remaining <= 0:
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

        is_opening = user_question == '__opening__'
        if not is_opening:
            conversation_history.append({'role': 'user', 'message': user_question})

        project_summary = build_project_summary(targets, scores)

        if is_opening:
            summary = (
                f"{project_summary}\n"
                f"Low-scoring dimensions: {dims_text}.\n"
                f"The student just uploaded their project. Ask your opening Socratic question based on what you can infer about this specific project."
            )
        else:
            summary = (
                f"{project_summary}\n"
                f"Low-scoring dimensions: {dims_text}.\n"
                f"Student said: {user_question}"
            )

        try:
            from socratic_turn1 import run as socratic_response
            ai_response = socratic_response(summary, low_dims, scores)
        except Exception as e:
            print(f"ERROR calling Gemini: {e}")
            ai_response = "Thinking about your answer... Consider: what blocks in Scratch let you check if something is true?"

        conversation_history.append({'role': 'ai', 'message': ai_response})
        if not is_opening:
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
