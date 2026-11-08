"""Local Windows short-form draft maker. No account or API key required."""
import csv
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
HOOKS = ('why', 'how', 'secret', 'mistake', 'never', 'best', 'learned', 'instead',
         'problem', 'reason', 'surprising', 'imagine', 'here is', "here's")


def run(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding='utf-8',
                            errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed:\n{result.stderr[-5000:]}')
    return result.stdout


def probe(source):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                           '-of', 'json', str(source)]))
    if not any(s['codec_type'] == 'video' for s in data['streams']):
        raise ValueError('Choose a video file.')
    return float(data['format']['duration']), any(s['codec_type'] == 'audio' for s in data['streams'])


def select_clips(segments, count=5, minimum=20, maximum=60):
    """Rank speech windows by simple hooks and sentence boundaries; not an AI editor."""
    candidates = []
    for i, first in enumerate(segments):
        selected = []
        for segment in segments[i:]:
            duration = segment['end'] - first['start']
            if duration > maximum:
                break
            selected.append(segment)
            if duration < minimum:
                continue
            text = ' '.join(s['text'].strip() for s in selected)
            opening = ' '.join(s['text'].strip() for s in selected[:2]).lower()
            words = re.findall(r'\w+', text.lower())
            score = sum(2 for hook in HOOKS if re.search(r'\b' + re.escape(hook) + r'\b', opening))
            score += 2 if segment['text'].strip().endswith(('.', '!', '?')) else 0
            score += len(set(words)) / max(len(words), 1)
            score -= abs(duration - 40) / 30
            if opening.startswith(('and ', 'but ', 'so ', 'because ')):
                score -= 2
            candidates.append((score, first['start'], segment['end'], text))
    chosen = []
    for score, start, end, text in sorted(candidates, key=lambda c: (-c[0], c[1])):
        if any(start < old['end'] and end > old['start'] for old in chosen):
            continue
        chosen.append({'name': f'clip_{len(chosen)+1:02d}', 'start': start, 'end': end, 'text': text})
        if len(chosen) >= count:
            break
    return sorted(chosen, key=lambda c: c['start'])


def load_plan(path, duration):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not {'name', 'start', 'end'}.issubset(reader.fieldnames or []):
            raise ValueError('CSV must have name,start,end columns, with timestamps in seconds.')
        clips = []
        for row in reader:
            start, end = float(row['start']), float(row['end'])
            if not all(math.isfinite(v) for v in (start, end)) or not 0 <= start < end <= duration + .1:
                raise ValueError(f'Invalid timestamps: {row}')
            name = re.sub(r'[^A-Za-z0-9_-]', '_', row['name'])[:70] or 'clip'
            clips.append({'name': f'{len(clips)+1:02d}_{name}', 'start': start, 'end': min(end, duration)})
    if not clips:
        raise ValueError('The CSV has no clips.')
    return clips


def ass_time(seconds):
    ticks = max(0, round(seconds * 100))
    return f'{ticks // 360000}:{ticks // 6000 % 60:02d}:{ticks // 100 % 60:02d}.{ticks % 100:02d}'


def ass_escape(text):
    return text.replace('\\', '').replace('{', '').replace('}', '').replace('\n', ' ').strip()


def write_captions(path, segments, start, end):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4,1,2,85,85,280,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    for segment in segments:
        if segment['end'] <= start or segment['start'] >= end:
            continue
        words = segment.get('words') or []
        if not words:
            # Existing transcripts without word timing retain their segment timing.
            words = [{'start': segment['start'], 'end': segment['end'], 'word': segment['text']}]
        words = [w for w in words if w['end'] > start and w['start'] < end]
        for offset in range(0, len(words), 6):
            group = words[offset:offset+6]
            a, b = max(start, group[0]['start']) - start, min(end, group[-1]['end']) - start
            if b <= a:
                continue
            text = ass_escape(' '.join(w['word'].strip() for w in group))
            events.append(f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{text}\n')
    path.write_text(header + ''.join(events), encoding='utf-8-sig')


def render(source, clip, folder, captions, crop):
    vf = ('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920'
          if crop else 'scale=1080:1920:force_original_aspect_ratio=decrease,'
          'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black')
    vf += ',setsar=1'
    if captions:
        vf += ',ass=captions.ass'
    output = folder / (clip['name'] + '.mp4')
    run(['ffmpeg', '-hide_banner', '-y', '-ss', str(clip['start']), '-i', str(source),
         '-t', str(clip['end'] - clip['start']), '-map', '0:v:0', '-map', '0:a:0?',
         '-vf', vf, '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
         '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
         '-movflags', '+faststart', str(output)], cwd=folder)
    return output


def process(source, csv_path, count, captions, crop, log):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('FFmpeg/FFprobe are missing. Reopen Start.cmd to install them.')
    duration, has_audio = probe(source)
    if not has_audio:
        raise ValueError('This workflow needs spoken audio. Choose a video with an audio track.')
    job = ROOT / 'output' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns())[-6:])
    job.mkdir(parents=True)
    log('Transcribing locally. First use downloads the speech model; long videos can take a while.')
    from faster_whisper import WhisperModel
    model = WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=4)
    stream, info = model.transcribe(str(source), word_timestamps=True, vad_filter=True)
    segments = []
    last_report = -30
    for s in stream:
        segments.append({'start': s.start, 'end': s.end, 'text': s.text.strip(),
                         'words': [{'start': w.start, 'end': w.end, 'word': w.word} for w in (s.words or [])]})
        if s.end - last_report >= 30:
            log(f'Transcribed through {int(s.end)//60}:{int(s.end)%60:02d} of {int(duration)//60}:{int(duration)%60:02d}')
            last_report = s.end
    if not segments:
        raise ValueError('No speech was detected. Try a video with clearer spoken audio.')
    (job / 'transcript.json').write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding='utf-8')
    (job / 'transcript.txt').write_text('\n'.join(f"[{s['start']:.3f} - {s['end']:.3f}] {s['text']}" for s in segments), encoding='utf-8')
    clips = load_plan(csv_path, duration) if csv_path else select_clips(segments, count=count)
    if not clips:
        raise ValueError(f'No 20–60 second speech windows found. Transcript saved in {job}. Use an exact-timestamp CSV for shorter footage.')
    with (job / 'clips.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'start', 'end'])
        writer.writeheader()
        writer.writerows({k: c[k] for k in writer.fieldnames} for c in clips)
    for i, clip in enumerate(clips, 1):
        log(f"Rendering {i}/{len(clips)}: {clip['start']:.1f}–{clip['end']:.1f}s")
        folder = job / clip['name']
        folder.mkdir()
        if captions:
            write_captions(folder / 'captions.ass', segments, clip['start'], clip['end'])
        render(source, clip, folder, captions, crop)
    log(f'Done. {len(clips)} vertical clips saved in {job}')
    return job


class App:
    def __init__(self, root):
        self.root = root
        root.title('Shortform — Local Draft Maker')
        root.geometry('780x580')
        self.messages = queue.Queue()
        self.source = tk.StringVar()
        self.plan = tk.StringVar()
        self.count = tk.IntVar(value=5)
        self.captions = tk.BooleanVar(value=True)
        self.crop = tk.BooleanVar(value=False)
        self.output = ROOT / 'output'
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Turn a long video into vertical draft clips', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Local transcription • No API key • Review automated selections before posting').pack(anchor='w', pady=(4, 16))
        self.file_row(frame, 'Video', self.source, [('Video files', '*.mp4 *.mov *.mkv *.webm *.avi'), ('All files', '*.*')])
        self.file_row(frame, 'Exact clips CSV (optional)', self.plan, [('CSV', '*.csv')])
        ttk.Label(frame, text='Leave CSV empty for automatic suggestions. Or use name,start,end columns in seconds.').pack(anchor='w', pady=6)
        options = ttk.Frame(frame)
        options.pack(fill='x', pady=10)
        ttk.Label(options, text='Suggested clips:').pack(side='left')
        ttk.Spinbox(options, from_=1, to=10, textvariable=self.count, width=4).pack(side='left', padx=8)
        ttk.Checkbutton(frame, text='Burn in readable captions', variable=self.captions).pack(anchor='w')
        ttk.Checkbutton(frame, text='Center crop to fill the frame (may cut off speakers)', variable=self.crop).pack(anchor='w')
        ttk.Label(frame, text='Default: preserve the whole image with padding. Output: 1080 × 1920 MP4.').pack(anchor='w', pady=6)
        self.button = ttk.Button(frame, text='Make Shorts', command=self.start)
        self.button.pack(fill='x', pady=12)
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill='x')
        self.logbox = tk.Text(frame, height=10, wrap='word', state='disabled')
        self.logbox.pack(fill='both', expand=True, pady=10)
        ttk.Button(frame, text='Open output folder', command=self.open_output).pack(anchor='e')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.busy = False
        self.poll()

    def file_row(self, frame, label, variable, types):
        ttk.Label(frame, text=label).pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(0, 8))
        ttk.Entry(row, textvariable=variable).pack(side='left', fill='x', expand=True)
        def browse():
            path = filedialog.askopenfilename(filetypes=types)
            if path:
                variable.set(path)
        ttk.Button(row, text='Browse…', command=browse).pack(side='right', padx=(8, 0))

    def start(self):
        source = Path(self.source.get()).expanduser().resolve()
        if not source.is_file():
            messagebox.showerror('Choose a video', 'Select an existing video file first.')
            return
        try:
            count = self.count.get()
            if not 1 <= count <= 10:
                raise ValueError()
        except (ValueError, tk.TclError):
            messagebox.showerror('Clip count', 'Choose between 1 and 10 clips.')
            return
        plan, captions, crop = self.plan.get().strip(), self.captions.get(), self.crop.get()
        self.busy = True
        self.button.config(state='disabled')
        self.progress.start()
        def work():
            try:
                out = process(source, plan, count, captions, crop, lambda s: self.messages.put(('log', s)))
                self.messages.put(('done', out))
            except Exception as e:
                self.messages.put(('error', str(e)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                self.logbox.config(state='normal')
                self.logbox.insert('end', str(value) + '\n')
                self.logbox.see('end')
                self.logbox.config(state='disabled')
                if kind in ('done', 'error'):
                    self.busy = False
                    self.progress.stop()
                    self.button.config(state='normal')
                    if kind == 'done':
                        self.output = value
                        messagebox.showinfo('Drafts ready', 'Clips are ready. Review cuts, captions, and framing before posting.')
                    else:
                        messagebox.showerror('Could not finish', value)
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def open_output(self):
        self.output.mkdir(parents=True, exist_ok=True)
        os.startfile(self.output)

    def close(self):
        if self.busy:
            messagebox.showinfo('Still working', 'Please let the current job finish before closing the app.')
        else:
            self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
