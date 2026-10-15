#!/usr/bin/env python3
"""Build Critter's original vector border collie animations, without downloads.

The geometry below is the editable artwork source, under the repository's MIT
license. Qt renders the SVG paths; Pillow writes transparent looping GIFs.
Run with the application's virtualenv. No API key or external artwork is used.
"""

import argparse
import math
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
STATES = {
    "idle_sleep": 160,
    "idle_walk": 100,
    "interact_wash": 100,
    "interact_wag": 80,
    "alert_run": 60,
}
FRAMES = 12
SIZE = 256
INK = "#303b39"
FUR = "#fff8e9"
SAGE = "#8faaa0"


def artwork(state, frame):
    """A small, round collie with a white blaze, socks and a sage collar."""
    phase = math.tau * frame / FRAMES
    wave, sway = math.sin(phase), math.cos(phase)
    sleeping = state == "idle_sleep"
    walking = state in ("idle_walk", "alert_run")
    washing = state == "interact_wash"
    happy = state == "interact_wag"
    bounce = (3 * math.cos(phase * 2) if walking else 1.5 * wave)
    tilt = (3 * wave if happy else -5 + 3 * wave if washing else 0)
    head_y = 12 if sleeping else 0
    tail_angle = (23 * wave if happy else 12 * wave if walking else 5 * wave)
    left_step = 8 * wave if walking else 0
    right_step = -left_step

    if sleeping:
        eyes = '''<path d="M92 117q10 10 20 0 M144 117q10 10 20 0"
            fill="none" stroke="#fff8e9" stroke-width="4" stroke-linecap="round"/>'''
    else:
        blink = (state == "interact_wag" and frame in (5, 6))
        if blink:
            eyes = '''<path d="M93 118q9 -10 19 0 M144 118q9 -10 19 0"
                fill="none" stroke="#fff8e9" stroke-width="4" stroke-linecap="round"/>'''
        else:
            eyes = '''<ellipse cx="103" cy="116" rx="12" ry="14" fill="#fff8e9"/>
                <ellipse cx="153" cy="116" rx="12" ry="14" fill="#fff8e9"/>
                <ellipse cx="106" cy="118" rx="7" ry="10" fill="#926e4e"/>
                <ellipse cx="150" cy="118" rx="7" ry="10" fill="#926e4e"/>
                <ellipse cx="107" cy="119" rx="4.5" ry="8" fill="#25312f"/>
                <ellipse cx="149" cy="119" rx="4.5" ry="8" fill="#25312f"/>
                <circle cx="109" cy="114" r="3" fill="white"/>
                <circle cx="151" cy="114" r="3" fill="white"/>'''

    mouth = ('<path d="M122 150q6 5 12 0" fill="none" stroke="#59635a" stroke-width="2.5" stroke-linecap="round"/>'
             if sleeping else '''<path d="M117 148q11 17 22 0" fill="#303b39"/>
             <path d="M122 152q6 -3 12 0v5q-6 10 -12 0z" fill="#e99996"/>
             <path d="M128 154v4" stroke="#c77979" stroke-width="1.5"/>''')

    ornaments = ""
    if sleeping:
        # Path lettering keeps the asset independent of installed fonts.
        ornaments = f'''<g transform="translate(0,{-3 * wave:.2f})" fill="none" stroke="#8faaa0" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M187 66h12l-12 12h12"/>
            <path d="M207 43h15l-15 15h15" opacity="{0.65 + 0.2 * sway:.2f}"/></g>'''
    elif happy:
        ornaments = f'''<path transform="translate(0,{-4 * wave:.2f})" d="M211 80c-15 -8 -13 -19 -5 -18q5 0 5 5q1 -6 7 -5c9 2 7 12 -7 18" fill="#dca09c"/>'''
    elif washing:
        ornaments = f'''<g fill="#d2e5e0" stroke="#8faaa0" stroke-width="2">
            <circle cx="64" cy="{132 - 5 * wave:.2f}" r="7"/>
            <circle cx="53" cy="{112 - 3 * sway:.2f}" r="4"/>
            <circle cx="62" cy="94" r="3"/></g>'''
    elif state == "alert_run":
        ornaments = f'''<g fill="none" stroke="#c5a36d" stroke-width="3.5" stroke-linecap="round">
            <path d="M206 70l9 -7 M210 84h13 M201 57l4 -10"/>
            <path d="M{29 + 5 * wave:.2f} 177h22 M{34 - 5 * wave:.2f} 190h14"/></g>'''

    paw = (f'''<g transform="rotate({-6 + 10 * wave:.2f} 105 173)">
               <path d="M92 183q-9 -20 3 -36q9 -15 20 -5q8 9 -4 21l-1 22" fill="{FUR}" stroke="{INK}" stroke-width="3"/>
               <path d="M99 146l5 5 M107 141l5 6" stroke="#c9c9ba" stroke-width="2" stroke-linecap="round"/>
               </g>''' if washing else "")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
      <title>Critter border collie — {state}</title>
      <ellipse cx="128" cy="225" rx="65" ry="8" fill="#a1a996" opacity="0.20"/>
      <g transform="translate(0,{bounce:.2f})">
        <g transform="rotate({tail_angle:.2f} 166 190)">
          <path d="M162 197q44 7 43 -30q-1 -13 -11 -20q5 28 -25 28" fill="{INK}"/>
          <path d="M194 147q14 8 11 24q-7 1 -13 -5q7 -7 2 -19" fill="{FUR}" stroke="{INK}" stroke-width="2"/>
        </g>
        <path d="M97 151q-30 26 -21 58q19 15 52 12q33 3 52 -12q9 -32 -21 -58z" fill="{INK}"/>
        <path d="M109 160q19 11 38 0l10 27l-14 -4l-15 27l-14 -27l-15 4z" fill="{FUR}"/>
        <ellipse cx="82" cy="213" rx="22" ry="10" fill="{INK}"/>
        <ellipse cx="174" cy="213" rx="22" ry="10" fill="{INK}"/>
        <g transform="translate(0,{left_step:.2f})">
          <path d="M93 185l-3 28q-3 12 15 12q15 0 13 -12l-3 -28" fill="{FUR}" stroke="{INK}" stroke-width="3"/>
          <path d="M99 218v5 M108 218v5" stroke="#c4c6b9" stroke-width="2" stroke-linecap="round"/>
        </g>
        <g transform="translate(0,{right_step:.2f})">
          <path d="M141 185l-3 28q-3 12 15 12q15 0 13 -12l-3 -28" fill="{FUR}" stroke="{INK}" stroke-width="3"/>
          <path d="M147 218v5 M156 218v5" stroke="#c4c6b9" stroke-width="2" stroke-linecap="round"/>
        </g>
        <path d="M92 162q36 17 72 0l-3 12q-33 15 -66 0z" fill="{SAGE}"/>
        <circle cx="128" cy="176" r="7" fill="#dbba7f" stroke="#b39565" stroke-width="1.5"/>
        <circle cx="128" cy="176" r="2" fill="#fff4d4"/>
        <g transform="translate(0,{head_y}) rotate({tilt:.2f} 128 137)">
          <path d="M77 92Q55 92 55 49q0 -12 12 -4l35 34 M154 79l35 -34q12 -8 12 4q0 43 -22 43" fill="{INK}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>
          <path d="M67 60l21 22l-20 -2z M189 60l-21 22l20 -2z" fill="#bd9290"/>
          <path d="M78 86q21 -25 50 -19q29 -6 50 19q14 19 15 50l8 6l-12 6l3 9l-15 0q-17 22 -49 20q-32 2 -49 -20l-15 0l3 -9l-12 -6l8 -6q1 -31 15 -50z" fill="{INK}" stroke="#26322f" stroke-width="2" stroke-linejoin="round"/>
          <path d="M119 69q9 -4 18 0l-1 24q-1 11 9 26l-17 24l-17 -24q10 -15 9 -26z" fill="{FUR}"/>
          <path d="M89 95l15 -3 M152 92l15 3" stroke="#92a298" stroke-width="3" stroke-linecap="round"/>
          {eyes}
          <path d="M128 135q-16 -10 -28 0q-10 12 5 23q23 18 46 0q15 -11 5 -23q-12 -10 -28 0" fill="{FUR}"/>
          <ellipse cx="128" cy="137" rx="10" ry="7" fill="#26322f"/>
          <ellipse cx="125" cy="135" rx="3.5" ry="1.5" fill="#64716b"/>
          <path d="M128 142v6 M117 146q5 7 11 1q6 6 11 -1" fill="none" stroke="#59635a" stroke-width="2" stroke-linecap="round"/>
          {mouth}
          <ellipse cx="91" cy="137" rx="7" ry="3.5" fill="#d49b97" opacity="0.7"/>
          <ellipse cx="165" cy="137" rx="7" ry="3.5" fill="#d49b97" opacity="0.7"/>
        </g>
        {paw}
      </g>
      {ornaments}
    </svg>'''
    return "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"


def render_svg(svg):
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Invalid vector artwork")
    canvas = QImage(SIZE, SIZE, QImage.Format.Format_RGBA8888)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    renderer.render(painter)
    painter.end()
    pixels = canvas.constBits()
    pixels.setsize(canvas.sizeInBytes())
    return Image.frombytes("RGBA", (SIZE, SIZE), bytes(pixels))


def gif_frame(rgba):
    # GIF supports binary alpha only. Reserve the last index for transparency;
    # do not introduce a white matte that would show on a dark desktop.
    indexed = rgba.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    palette = (indexed.getpalette() or [])[:765]
    indexed.putpalette(palette + [0] * (768 - len(palette)))
    indexed.paste(255, mask=rgba.getchannel("A").point(lambda a: 255 if a < 128 else 0))
    indexed.info["transparency"] = 255
    return indexed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "assets/animations/border_collie")
    args = parser.parse_args()
    app = QGuiApplication.instance() or QGuiApplication([])
    args.output.mkdir(parents=True, exist_ok=True)
    for state, duration in STATES.items():
        frames = [gif_frame(render_svg(artwork(state, index))) for index in range(FRAMES)]
        target = args.output / f"{state}.gif"
        frames[0].save(target, save_all=True, append_images=frames[1:],
                       duration=duration, loop=0, disposal=2, transparency=255, optimize=False)
        print(f"{target.name}: {FRAMES} frames, {duration} ms/frame")
    (args.output / "border_collie.svg").write_text(artwork("interact_wag", 0), encoding="utf-8")
    # Keep the Qt application alive until every SVG has been rendered.
    del app


if __name__ == "__main__":
    main()
