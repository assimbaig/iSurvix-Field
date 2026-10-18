"""Probe local vision with a synthetic diagram; never reads project photos."""
import base64
import io
import json
import sys
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from PIL import Image, ImageDraw


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def call(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request('http://127.0.0.1:11434' + path, data=body,
                      headers={'Content-Type': 'application/json'})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=180) as response:
        return json.load(response)


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else 'qwen3.5:4b'
    installed = call('/api/tags').get('models', [])
    if not any(item.get('name') == model and not item.get('remote_model') and
               not item.get('remote_host') and not any(alias in model.lower() for alias in ('-cloud', ':cloud')) for item in installed):
        raise RuntimeError('Select an installed local model.')
    details = call('/api/show', {'model': model})
    if 'vision' not in details.get('capabilities', []) or details.get('remote_model') or details.get('remote_host'):
        raise RuntimeError('The installed model does not report local vision capability.')
    print('Verified capabilities:', ', '.join(details['capabilities']), flush=True)
    image = Image.new('RGB', (640, 360), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 90, 220, 250), fill='red')
    draw.ellipse((400, 90, 560, 250), fill='blue')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    result = call('/api/chat', {
        'model': model, 'stream': False, 'think': False,
        'messages': [{'role': 'user', 'content': 'Describe the two colored shapes and their left/right positions in one sentence.',
                      'images': [base64.b64encode(stream.getvalue()).decode('ascii')]}],
        'options': {'temperature': 0, 'num_predict': 160},
    })
    answer = result.get('message', {}).get('content', '')
    print('Synthetic image response:', answer, flush=True)
    if not all(word in answer.lower() for word in ('red', 'blue', 'square', 'circle')):
        raise RuntimeError('Vision response did not identify the synthetic shapes; review model readiness.')
    print('PASS: native image input returned the expected colored shapes.')


if __name__ == '__main__':
    main()
