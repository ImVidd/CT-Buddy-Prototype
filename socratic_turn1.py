import sys
import json
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=API_KEY)

DIM_HINTS = {
    'Logic': "when sprites need to make decisions or check conditions",
    'Abstraction': "which actions repeat across sprites and could be grouped into a custom block",
    'Data Representation': "what information the game needs to remember using variables or lists",
    'Math Operators': "where numbers, calculations, or comparisons are used in the project",
}

def build_prompt(summary, low_dims, scores, final=False):
    score_text = '\n'.join([f'  {k}: {v}/4' for k, v in scores.items()])
    dims_text = ', '.join(low_dims)
    hints = '\n'.join([f'  - {d}: think about {DIM_HINTS.get(d, d)}' for d in low_dims])

    if final:
        return f"""You are CT-Buddy, a Socratic tutor helping a student improve their Scratch project.
The conversation is ending. Write a warm, encouraging wrap-up (3-5 sentences) that:
1. Acknowledges what the student shared
2. Names the low-scoring dimension(s): {dims_text}
3. Tells them specifically which Scratch blocks or concepts to add to improve each
4. Encourages them to upload a revised version

Project description:
{summary}

Dr. Scratch scores:
{score_text}
"""

    return f"""You are CT-Buddy, a Socratic tutor helping a school student improve their Scratch project.
The student scored 0 out of 4 on: {dims_text}

Do NOT give them the answer. Ask ONE guiding question that helps them think about why one of these scores might be low.

Dimension guidance:
{hints}

Project description:
{summary}

Dr. Scratch scores:
{score_text}

Your job:
- Ask ONE single guiding question about one of the low-scoring dimensions
- Do NOT name the specific Scratch block or give away the solution
- Do NOT use technical jargon the student would not know
- Be warm, encouraging, and curious
- Keep it short — one question only
"""

def run(summary, low_dims, scores, final=False):
    prompt = build_prompt(summary, low_dims, scores, final=final)

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )

    print('\nCT-Buddy says:')
    print(response.text)
    return response.text

if __name__ == '__main__':
    if len(sys.argv) > 1:
        data = json.loads(sys.argv[1])
        run(data['summary'], data['low_dims'], data['scores'])
    else:
        print("Please provide project data.")
