import json, subprocess, sys, imageio_ffmpeg
ff = imageio_ffmpeg.get_ffmpeg_exe()
meta = json.load(open('frames.json')); fr = meta['frames']
t0 = fr[0]['t']
lines = []
for i, f in enumerate(fr):
    nxt = fr[i + 1]['t'] if i + 1 < len(fr) else meta['endWall']
    lines.append(f"file 'frames/{f['name']}'\nduration {max(nxt - f['t'], 0.001):.4f}\n")
lines.append(f"file 'frames/{fr[-1]['name']}'\n")
open('list.txt', 'w').write(''.join(lines))
dur = meta['endWall'] - t0
print('first frame after start: %.2fs' % (t0 - meta['startWall']))
out = sys.argv[1] if len(sys.argv) > 1 else 'flightline_demo.mp4'
vf = f"fps=30,scale=1920:1080:flags=lanczos:in_range=pc:out_range=tv,fade=t=in:st=0:d=0.6,fade=t=out:st={dur-0.8:.2f}:d=0.8,format=yuv420p"
subprocess.run([ff, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-vf', vf,
                '-t', f'{dur:.2f}', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-movflags', '+faststart', out], check=True)
print('wrote', out, f'{dur:.1f}s')
