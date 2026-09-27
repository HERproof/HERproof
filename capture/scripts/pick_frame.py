"""Pick the frame that differs most from the first (resting) frame."""
import sys, glob
from PIL import Image, ImageChops, ImageStat
frames = sorted(glob.glob(sys.argv[1] + "/f_*.jpg"))
base = Image.open(frames[0]).convert("L")
best, score = frames[0], -1
for f in frames[1:]:
    d = ImageStat.Stat(ImageChops.difference(base, Image.open(f).convert("L"))).mean[0]
    if d > score: best, score = f, d
print(best)
