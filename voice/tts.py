#!/usr/bin/env python3
"""Text to speech, on any platform.

  macOS   `say -v <voice>`            (built-in; the reference build's stand-in)
  Linux   Piper — local neural TTS    (`piper` on PATH + a .onnx voice model)
  any     none                        (silent; the HUD still types the answer)

Backend comes from config persona.tts: "say" | "piper" | "auto" (default) | "none".
Voice comes from persona.voice: a `say` voice name, or a path to a Piper .onnx model.
speak() blocks until the utterance finishes so the service can flip SPEAKING -> IDLE.
"""
import os, platform, shutil, subprocess, tempfile

IS_MAC = platform.system() == 'Darwin'


def choose(cfg_tts='auto'):
    if cfg_tts in ('say', 'piper', 'none'):
        return cfg_tts
    if IS_MAC and shutil.which('say'):
        return 'say'
    if shutil.which('piper'):
        return 'piper'
    return 'none'


def _player():
    for p in ('aplay', 'paplay', 'afplay', 'ffplay'):
        if shutil.which(p):
            return p
    return None


def speak(text, voice='Flo', backend='auto', timeout=60):
    b = choose(backend)
    if b == 'say':
        subprocess.run(['say', '-v', voice, text], timeout=timeout)
        return b
    if b == 'piper':
        # piper writes a wav; play it with whatever the box has
        model = voice if voice.endswith('.onnx') else os.path.expanduser(
            '~/.local/share/piper/en_GB-alba-medium.onnx')
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav = f.name
        subprocess.run(['piper', '--model', model, '--output_file', wav],
                       input=text, text=True, timeout=timeout, capture_output=True)
        p = _player()
        if p:
            args = [p, wav] if p != 'ffplay' else ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', wav]
            subprocess.run(args, timeout=timeout)
        try:
            os.unlink(wav)
        except OSError:
            pass
        return b
    return 'none'


if __name__ == '__main__':
    import sys
    print('backend:', choose())
    speak(' '.join(sys.argv[1:]) or 'Text to speech is working.')
