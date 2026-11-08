import json
from pathlib import Path
import shutil
import tempfile
import unittest

import app


class ClipTests(unittest.TestCase):
    def test_selection_stays_in_bounds_and_does_not_overlap(self):
        segments = [
            {'start': i * 5, 'end': (i + 1) * 5,
             'text': 'Here is why this mistake matters.' if i % 8 == 0 else 'A useful complete sentence.'}
            for i in range(40)
        ]
        clips = app.select_clips(segments, count=3)
        self.assertEqual(len(clips), 3)
        for clip in clips:
            self.assertGreaterEqual(clip['start'], 0)
            self.assertLessEqual(clip['end'], 200)
            self.assertTrue(20 <= clip['end'] - clip['start'] <= 60)
        for left, right in zip(clips, clips[1:]):
            self.assertLessEqual(left['end'], right['start'])

    def test_short_transcript_does_not_invent_clips(self):
        self.assertEqual(app.select_clips([{'start': 0, 'end': 5, 'text': 'Hello.'}]), [])

    def test_csv_accepts_exact_times_and_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'clips.csv'
            path.write_text('name,start,end\n../unsafe,1.25,4.5\n', encoding='utf-8')
            clips = app.load_plan(path, 10)
            self.assertEqual(clips[0]['start'], 1.25)
            self.assertNotIn('/', clips[0]['name'])
            for start, end in [('nan', '5'), ('0', 'inf'), ('-1', '4'), ('5', '4'), ('0', '12')]:
                path.write_text(f'name,start,end\nbad,{start},{end}\n', encoding='utf-8')
                with self.assertRaises(ValueError):
                    app.load_plan(path, 10)

    def test_caption_timing_is_relative_and_clamped(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'captions.ass'
            app.write_captions(path, [{'start': 8, 'end': 14, 'text': 'hello',
                'words': [{'start': 8, 'end': 11, 'word': '{hello}'},
                          {'start': 11, 'end': 14, 'word': 'world'}]}], 10, 12)
            captions = path.read_text(encoding='utf-8-sig')
            self.assertIn('0:00:00.00,0:00:02.00', captions)
            self.assertIn('hello world', captions)
            self.assertNotIn('{hello}', captions)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_vertical_render_with_captions_and_path_spaces(self):
        with tempfile.TemporaryDirectory(prefix='shortform test ') as d:
            folder = Path(d)
            source = folder / 'source video.mp4'
            app.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                     'color=c=blue:s=320x180:r=30:d=2', '-f', 'lavfi', '-i',
                     'sine=frequency=440:duration=2', '-c:v', 'libx264',
                     '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(source)])
            segments = [{'start': 0, 'end': 2, 'text': 'Caption render test.'}]
            app.write_captions(folder / 'captions.ass', segments, .25, 1.25)
            for crop in (False, True):
                output = app.render(source, {'name': f'test_{crop}', 'start': .25, 'end': 1.25}, folder, True, crop)
                duration, audio = app.probe(output)
                self.assertAlmostEqual(duration, 1, delta=.15)
                self.assertTrue(audio)
                data = json.loads(app.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)]))
                video = next(s for s in data['streams'] if s['codec_type'] == 'video')
                self.assertEqual((video['width'], video['height']), (1080, 1920))


if __name__ == '__main__':
    unittest.main()
