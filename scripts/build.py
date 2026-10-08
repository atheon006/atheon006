#!/usr/bin/env python3
"""Visuels SVG du README de profil.

    python scripts/build.py static            bannière, boutons, badges, stack et contact → assets/
    python scripts/build.py stats <dossier>   carte d'activité, lue sur l'API GitHub (variable GITHUB_TOKEN)

Les polices Geist et Geist Mono (licence OFL, scripts/fonts) sont incorporées dans chaque SVG,
réduites aux seuls caractères utilisés. Icônes : Simple Icons (CC0) et Bootstrap Icons (MIT).
Dépendances : pip install fonttools brotli
"""
import base64
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

USER = 'atheon006'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
ASSETS = os.path.join(ROOT, 'assets')

FONTS = {'sans': f'{SCRIPTS}/fonts/geist.woff2', 'mono': f'{SCRIPTS}/fonts/geist-mono.woff2'}
FAMILY = {'sans': 'Geist', 'mono': 'Geist Mono'}

THEMES = {
    'dark': {
        'bg': '#0a0a0c', 'panel': '#111114', 'tile': '#16161a', 'line': 'rgba(255,255,255,.09)',
        'line2': 'rgba(255,255,255,.15)', 'fg': '#ededef', 'muted': '#a1a1aa', 'dim': '#8a8a93',
        'accent': '#ff7a30', 'ink': '#ffb07f', 'ok': '#4ade80', 'track': '#1d1d22', 'on_accent': '#09090b',
    },
    'light': {
        'bg': '#ffffff', 'panel': '#fafafa', 'tile': '#f4f4f5', 'line': 'rgba(9,9,11,.10)',
        'line2': 'rgba(9,9,11,.16)', 'fg': '#09090b', 'muted': '#52525b', 'dim': '#6b6b74',
        'accent': '#ff7a30', 'ink': '#c2410c', 'ok': '#15803d', 'track': '#ececef', 'on_accent': '#09090b',
    },
}
# La bannière et la carte de contact gardent l'identité sombre du portfolio dans les deux thèmes.
BRAND = THEMES['dark']

EASE = 'cubic-bezier(.2,.7,.2,1)'


# ---------------------------------------------------------------- texte et polices

_metrics = {}


def _font_at(kind, weight):
    key = (kind, weight)
    if key not in _metrics:
        font = instancer.instantiateVariableFont(TTFont(FONTS[kind]), {'wght': weight})
        _metrics[key] = (font.getBestCmap(), font['hmtx'].metrics, font['head'].unitsPerEm)
    return _metrics[key]


def text_width(s, size, kind='sans', weight=400, tracking=0.0):
    """Largeur approximative d'un texte (sans crénage), en pixels."""
    cmap, hmtx, upm = _font_at(kind, weight)
    units = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else hmtx['.notdef'][0] for c in s)
    return units * size / upm + tracking * size * max(len(s) - 1, 0)


def font_face(kind, chars):
    font = TTFont(FONTS[kind])
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = ['kern', 'liga', 'calt', 'tnum', 'case']
    opts.name_IDs = []
    opts.hinting = False
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=''.join(sorted(chars)))
    sub.subset(font)
    font.flavor = 'woff2'
    buf = io.BytesIO()
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'{FAMILY[kind]}';font-weight:100 900;src:url(data:font/woff2;base64,{data}) format('woff2')}}"


def esc(s):
    return html.escape(str(s), quote=True)


class Svg:
    """Petit assembleur de SVG qui note les caractères utilisés pour réduire les polices."""

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.chars = {'sans': set(), 'mono': set()}
        self.css, self.defs, self.body = [], [], []

    def text(self, x, y, s, size, kind='sans', weight=400, fill='currentColor', anchor='start',
             tracking=0.0, cls='', extra=''):
        self.chars[kind].update(s)
        classes = ('m' if kind == 'mono' else 's') + (f' {cls}' if cls else '')
        attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'class="{classes}"',
                 f'font-size="{size}"', f'font-weight="{weight}"', f'fill="{fill}"']
        if anchor != 'start':
            attrs.append(f'text-anchor="{anchor}"')
        if tracking:
            attrs.append(f'letter-spacing="{tracking * size:.2f}"')
        if extra:
            attrs.append(extra)
        return f'<text {" ".join(attrs)}>{esc(s)}</text>'

    def spans(self, x, y, parts, size, kind='sans', anchor='start', cls='', extra=''):
        """Texte en plusieurs morceaux : parts = [(texte, poids, couleur, taille ou None)]."""
        out = []
        for s, weight, fill, sz in parts:
            self.chars[kind].update(s)
            size_attr = f' font-size="{sz}"' if sz else ''
            out.append(f'<tspan font-weight="{weight}" fill="{fill}"{size_attr}>{esc(s)}</tspan>')
        classes = ('m' if kind == 'mono' else 's') + (f' {cls}' if cls else '')
        a = f' text-anchor="{anchor}"' if anchor != 'start' else ''
        e = f' {extra}' if extra else ''
        return f'<text x="{x:.1f}" y="{y:.1f}" class="{classes}" font-size="{size}"{a}{e}>{"".join(out)}</text>'

    def add(self, *parts):
        self.body.extend(parts)

    def render(self):
        faces = ''.join(font_face(k, c | {' '}) for k, c in self.chars.items() if c)
        base = (".s{font-family:'Geist',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}"
                ".m{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
                '.tn{font-variant-numeric:tabular-nums}')
        css = faces + base + ''.join(self.css)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="title">'
                f'<title id="title">{esc(self.title)}</title><defs><style>{css}</style>{"".join(self.defs)}</defs>'
                f'{"".join(self.body)}</svg>')


# ---------------------------------------------------------------- icônes et couleurs

def icon(name, x, y, size, fill):
    raw = open(f'{SCRIPTS}/icons/{name}.svg', encoding='utf-8').read()
    vx, vy, vw, vh = (float(v) for v in re.search(r'viewBox="([^"]+)"', raw).group(1).split())
    paths = re.findall(r'\sd="([^"]+)"', raw)
    k = size / max(vw, vh)
    ox, oy = x + (size - vw * k) / 2 - vx * k, y + (size - vh * k) / 2 - vy * k
    return (f'<g transform="translate({ox:.2f} {oy:.2f}) scale({k:.4f})" fill="{fill}">'
            + ''.join(f'<path d="{d}"/>' for d in paths) + '</g>')


def _rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb):
    return '#' + ''.join(f'{round(c * 255):02x}' for c in rgb)


def _lum(rgb):
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def readable(color, bg, minimum=3.0):
    """Éclaircit (fond sombre) ou fonce (fond clair) une couleur de marque jusqu'à un contraste suffisant."""
    c, b = _rgb(color), _rgb(bg)
    target = (1, 1, 1) if _lum(b) < 0.5 else (0, 0, 0)
    t, out = 0.0, c
    while _contrast(out, b) < minimum and t < 1:
        t += 0.04
        out = tuple(ci + (ti - ci) * t for ci, ti in zip(c, target))
    return _hex(out)


# ---------------------------------------------------------------- fond « sombre premium »

def brand_background(svg, w, h, radius, glow_at=(0.86, -0.05), glow2_at=(0.04, 1.15)):
    svg.defs.append(
        f'<radialGradient id="glow" cx="{glow_at[0]}" cy="{glow_at[1]}" r="0.75">'
        '<stop offset="0" stop-color="#ff7a30" stop-opacity=".30"/><stop offset=".45" stop-color="#ff7a30" stop-opacity=".08"/>'
        '<stop offset="1" stop-color="#ff7a30" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="glow2" cx="{glow2_at[0]}" cy="{glow2_at[1]}" r="0.6">'
        '<stop offset="0" stop-color="#ff7a30" stop-opacity=".10"/><stop offset="1" stop-color="#ff7a30" stop-opacity="0"/></radialGradient>'
        '<pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse">'
        '<path d="M44 0H0V44" fill="none" stroke="#fff" stroke-opacity=".05"/></pattern>'
        f'<radialGradient id="gridfade" cx="{glow_at[0]}" cy="{max(min(glow_at[1], 1), 0)}" r="0.9"><stop offset="0" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="gridmask"><rect width="{w}" height="{h}" fill="url(#gridfade)"/></mask>'
        '<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" '
        'numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>'
        f'<clipPath id="frame"><rect width="{w}" height="{h}" rx="{radius}"/></clipPath>'
    )
    svg.add(
        f'<g clip-path="url(#frame)"><rect width="{w}" height="{h}" fill="#09090b"/>'
        f'<rect width="{w}" height="{h}" fill="url(#glow)"/><rect width="{w}" height="{h}" fill="url(#glow2)"/>'
        f'<rect width="{w}" height="{h}" fill="url(#grid)" mask="url(#gridmask)"/>'
        f'<rect width="{w}" height="{h}" filter="url(#grain)" opacity=".07"/></g>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{radius - .5}" fill="none" stroke="#fff" stroke-opacity=".10"/>'
    )


MOTION_CSS = (
    '@keyframes up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}'
    '@keyframes fade{from{opacity:0}to{opacity:1}}'
    '@keyframes ping{0%{transform:scale(1);opacity:.7}80%,100%{transform:scale(2.6);opacity:0}}'
    f'.up{{animation:up .9s {EASE} both;animation-delay:var(--d,0s)}}'
    '.ping{transform-box:fill-box;transform-origin:center;animation:ping 2.2s cubic-bezier(0,0,.2,1) infinite}'
)
REDUCED_CSS = '@media (prefers-reduced-motion:reduce){*{animation:none!important}}'


def live_dot(cx, cy, color, r=4):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" class="ping"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')


# ---------------------------------------------------------------- bannière

PRODUCTS = [
    ('ParentEcole', 'parentecole.web.app', 'live'),
    ('XERA1', 'xera1.xyz', 'live'),
    ('Objets perdus', 'objetsperdus.online', 'live'),
    ('ATLAS', 'atlas-web-portal.vercel.app', 'beta'),
]
ROLES = [
    ('CTO', 'ParentEcole'),
    ('CTO', 'XERA1'),
    ('Cofondateur', 'Objets perdus'),
    ('Je construis', 'ATLAS, la marketplace de Goma'),
]
ROLE_TIME = 3.2


def status_pill(svg, right, cy, status, t):
    label = 'EN LIGNE' if status == 'live' else 'BÊTA'
    color = t['ok'] if status == 'live' else t['accent']
    size = 10.5
    w = text_width(label, size, 'mono', 500, 0.08) + 34
    x = right - w
    return (f'<rect x="{x:.1f}" y="{cy - 11}" width="{w:.1f}" height="22" rx="11" fill="{color}" fill-opacity=".10" '
            f'stroke="{color}" stroke-opacity=".28"/>'
            f'<circle cx="{x + 13:.1f}" cy="{cy}" r="3" fill="{color}"/>'
            + svg.text(x + 22, cy + 3.8, label, size, 'mono', 500, color, tracking=0.08))


def banner():
    t = BRAND
    W, H = 1200, 400
    svg = Svg(W, H, 'Ready Kalonda (Athéon) — développeur web, mobile et systèmes à Goma, RD Congo. '
                    'CTO de ParentEcole et de XERA1, cofondateur d’Objets perdus.')
    svg.css.append(MOTION_CSS)
    cycle = ROLE_TIME * len(ROLES)
    svg.css.append(
        '@keyframes roll{0%{opacity:0;transform:translateY(9px)}3%,22%{opacity:1;transform:none}'
        '25%,100%{opacity:0;transform:translateY(-9px)}}'
        f'.role{{opacity:0;animation:roll {cycle}s {EASE} infinite both}}'
        '@keyframes blink{50%{opacity:0}}.caret{animation:blink 1.1s steps(1) infinite}'
        '@media (prefers-reduced-motion:reduce){*{animation:none!important}.first{opacity:1}}'
    )
    brand_background(svg, W, H, 28)

    # En-tête : monogramme, adresse du portfolio, disponibilité
    svg.add('<g class="up" style="--d:.05s">',
            '<rect x="56" y="48" width="36" height="36" rx="9" fill="#ededef"/>',
            svg.text(74, 71.5, 'RK', 14, 'sans', 700, '#09090b', 'middle', -0.02),
            svg.text(106, 71, 'readykalonda.vercel.app', 13.5, 'mono', 400, t['dim']),
            '</g>')
    avail = 'Disponible pour des missions'
    aw = text_width(avail, 14, 'sans', 450) + 46
    ax = 1144 - aw
    svg.add('<g class="up" style="--d:.1s">',
            f'<rect x="{ax:.1f}" y="48" width="{aw:.1f}" height="36" rx="18" fill="#fff" fill-opacity=".03" stroke="#fff" stroke-opacity=".10"/>',
            live_dot(ax + 20, 66, t['ok']),
            svg.text(ax + 33, 71, avail, 14, 'sans', 450, t['muted']),
            '</g>')

    # Identité
    svg.defs.append('<linearGradient id="name" x1="0" y1="0" x2="0" y2="1">'
                    '<stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#b4b4bc"/></linearGradient>')
    svg.add('<g class="up" style="--d:.15s">', svg.text(57, 156, 'ATHÉON · GOMA, RD CONGO', 13, 'mono', 500, t['ink'], tracking=0.16), '</g>')
    svg.add('<g class="up" style="--d:.22s">', svg.text(52, 238, 'Ready Kalonda', 88, 'sans', 600, 'url(#name)', tracking=-0.045), '</g>')
    svg.add('<g class="up" style="--d:.3s">', svg.text(56, 284, 'Développeur web, mobile & systèmes', 24, 'sans', 400, t['muted']), '</g>')

    # Rôles qui défilent
    rows = []
    for i, (role, what) in enumerate(ROLES):
        lead = f'{role} · ' if role != 'Je construis' else f'{role} '
        x_end = 82 + text_width(lead, 17, 'mono', 500) + text_width(what, 17, 'mono', 400)
        rows.append(
            f'<g class="role{" first" if i == 0 else ""}" style="animation-delay:{i * ROLE_TIME:.1f}s">'
            + svg.spans(82, 340, [(lead, 500, t['fg'], None), (what, 400, t['muted'], None)], 17, 'mono')
            + f'<rect class="caret" x="{x_end + 6:.1f}" y="326" width="9" height="18" rx="1.5" fill="{t["accent"]}"/></g>')
    svg.add('<g class="up" style="--d:.38s">', svg.text(57, 340, '›', 19, 'mono', 600, t['accent']), *rows, '</g>')

    # Produits en ligne
    px, py, pw = 772, 108, 372
    row_h = 52
    ph = 44 + row_h * len(PRODUCTS)
    svg.add('<g class="up" style="--d:.3s">',
            f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="18" fill="#fff" fill-opacity=".025" stroke="#fff" stroke-opacity=".09"/>',
            svg.text(px + 22, py + 29, 'EN PRODUCTION', 11, 'mono', 500, t['dim'], tracking=0.16),
            svg.text(px + pw - 22, py + 29, f'{len(PRODUCTS)} PRODUITS', 11, 'mono', 500, t['dim'], 'end', 0.16),
            '</g>')
    for i, (name, domain, status) in enumerate(PRODUCTS):
        top = py + 44 + i * row_h
        svg.add(f'<g class="up" style="--d:{.42 + i * .08:.2f}s">',
                f'<path d="M{px + 22} {top}H{px + pw - 22}" stroke="#fff" stroke-opacity=".07"/>',
                svg.text(px + 22, top + 23, name, 16, 'sans', 550, t['fg']),
                svg.text(px + 22, top + 41, domain, 11.5, 'mono', 400, t['dim']),
                status_pill(svg, px + pw - 22, top + row_h / 2, status, t),
                '</g>')
    return svg.render()


# ---------------------------------------------------------------- boutons de liens

LINKS = [
    ('portfolio', 'Portfolio', None, True),
    ('linkedin', 'LinkedIn', ('linkedin', '#0A66C2'), False),
    ('email', 'E-mail', ('gmail', '#EA4335'), False),
    ('discord', 'Discord', ('discord', '#5865F2'), False),
    ('reddit', 'Reddit', ('reddit', '#FF4500'), False),
]


def globe(x, y, size, color):
    k = size / 24
    return (f'<g transform="translate({x} {y}) scale({k:.4f})" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/>'
            '<path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></g>')


def button(label, brand, primary, t):
    size, h, pad, gap, ico = 15, 44, 18, 10, 18
    w = round(pad + ico + gap + text_width(label, size, 'sans', 550) + pad + (14 if primary else 0))
    svg = Svg(w, h, label)
    if primary:
        svg.add(f'<rect width="{w}" height="{h}" rx="{h / 2}" fill="{t["accent"]}"/>',
                globe(pad, (h - ico) / 2, ico, t['on_accent']),
                svg.text(pad + ico + gap, 27.5, label, size, 'sans', 600, t['on_accent']),
                f'<path d="M{w - pad - 9} {h / 2 - 4.5}l4.5 4.5-4.5 4.5" fill="none" stroke="{t["on_accent"]}" '
                'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    else:
        name, color = brand
        bg = t['tile'] if t is THEMES['dark'] else '#ffffff'
        svg.add(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{(h - 1) / 2}" fill="{bg}" stroke="{t["line2"]}"/>',
                icon(name, pad, (h - ico) / 2, ico, readable(color, bg, 3.0)),
                svg.text(pad + ico + gap, 27.5, label, size, 'sans', 550, t['fg']))
    return svg.render()


def badge(status, t):
    label = {'live': 'En ligne', 'beta': 'Bêta', 'proto': 'Prototype'}[status]
    color = {'live': t['ok'], 'beta': readable(t['accent'], t['bg'], 3.0), 'proto': t['dim']}[status]
    size = 12
    w = round(text_width(label, size, 'sans', 550) + 30)
    svg = Svg(w, 22, label)
    svg.add(f'<rect x=".5" y=".5" width="{w - 1}" height="21" rx="10.5" fill="{color}" fill-opacity=".10" stroke="{color}" stroke-opacity=".30"/>',
            f'<circle cx="11" cy="11" r="3" fill="{color}"/>',
            svg.text(19, 15.2, label, size, 'sans', 550, color))
    return svg.render()


# ---------------------------------------------------------------- stack

STACK = [
    ('LANGAGES', [('TypeScript', 'typescript', '#3178C6'), ('JavaScript', 'javascript', '#F7DF1E'), ('Dart', 'dart', '#0175C2'),
                  ('Python', 'python', '#3776AB'), ('HTML', 'html5', '#E34F26'), ('CSS', 'css', '#663399')]),
    ('FRONT-END', [('React', 'react', '#61DAFB'), ('Astro', 'astro', '#BC52EE'), ('Tailwind CSS', 'tailwindcss', '#06B6D4'),
                   ('Vite', 'vite', '#9135FF'), ('Angular', 'angular', '#DD0031')]),
    ('MOBILE & IA', [('Flutter', 'flutter', '#02569B'), ('Capacitor', 'capacitor', '#119EFF'), ('Android', 'android', '#3DDC84'),
                     ('Gemini API', 'googlegemini', '#8E75B2')]),
    ('BACK-END & DONNÉES', [('Node.js', 'nodedotjs', '#5FA04E'), ('NestJS', 'nestjs', '#E0234E'), ('Firebase', 'firebase', '#DD2C00'),
                            ('Supabase', 'supabase', '#3FCF8E'), ('PostgreSQL', 'postgresql', '#4169E1'), ('GraphQL', 'graphql', '#E10098'),
                            ('MongoDB', 'mongodb', '#47A248'), ('MySQL', 'mysql', '#4479A1')]),
    ('OUTILS', [('Git', 'git', '#F03C2E'), ('GitHub Actions', 'githubactions', '#2088FF'), ('Docker', 'docker', '#2496ED'),
                ('Vercel', 'vercel', '#000000'), ('Linux', 'linux', '#FCC624')]),
]


def stack(t):
    W, pad, label_w, step, box, row_h = 1000, 36, 196, 95, 52, 98
    H = pad * 2 + row_h * len(STACK) - 24
    svg = Svg(W, H, 'Stack technique : ' + ', '.join(n for _, items in STACK for n, _, _ in items))
    svg.css.append(MOTION_CSS + REDUCED_CSS)
    svg.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="{t["panel"]}" stroke="{t["line"]}"/>')
    n = 0
    for r, (group, items) in enumerate(STACK):
        top = pad + r * row_h
        if r:
            svg.add(f'<path d="M{pad} {top - 13}H{W - pad}" stroke="{t["line"]}"/>')
        svg.add(svg.text(pad, top + box / 2 + 4, group, 11.5, 'mono', 500, t['dim'], tracking=0.12))
        for i, (name, slug, color) in enumerate(items):
            x = pad + label_w + i * step
            cx = x + box / 2
            svg.add(f'<g class="up" style="--d:{.04 * n:.2f}s">',
                    f'<rect x="{x + .5}" y="{top + .5}" width="{box - 1}" height="{box - 1}" rx="14" fill="{t["tile"]}" stroke="{t["line"]}"/>',
                    icon(slug, x + 13, top + 13, 26, readable(color, t['tile'], 2.6)),
                    svg.text(cx, top + box + 18, name, 11.5, 'sans', 450, t['muted'], 'middle'),
                    '</g>')
            n += 1
    return svg.render()


# ---------------------------------------------------------------- contact

def contact():
    t = BRAND
    W, H = 1200, 250
    svg = Svg(W, H, 'Un projet en tête ? Écrivez-moi : readykalonda38@gmail.com')
    svg.css.append(MOTION_CSS + REDUCED_CSS)
    brand_background(svg, W, H, 28, glow_at=(0.92, 1.1), glow2_at=(0.02, -0.2))
    svg.add('<g class="up">', svg.text(57, 82, 'CONTACT', 13, 'mono', 500, t['ink'], tracking=0.16), '</g>',
            '<g class="up" style="--d:.08s">', svg.text(54, 140, 'Un projet en tête ? Parlons-en.', 46, 'sans', 600, t['fg'], tracking=-0.035), '</g>',
            '<g class="up" style="--d:.16s">', svg.text(56, 182, 'Je travaille en français et en anglais, depuis Goma ou à distance.', 18, 'sans', 400, t['muted']), '</g>')
    label = 'readykalonda38@gmail.com'
    bw = text_width(label, 16, 'sans', 600) + 84
    bx, by = 1144 - bw, 101
    svg.add('<g class="up" style="--d:.24s">',
            f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="52" rx="26" fill="{t["accent"]}"/>',
            icon('gmail', bx + 22, by + 17, 18, t['on_accent']),
            svg.text(bx + 50, by + 31.5, label, 16, 'sans', 600, t['on_accent']),
            f'<path d="M{bx + bw - 28:.1f} {by + 21.5}l4.5 4.5-4.5 4.5" fill="none" stroke="{t["on_accent"]}" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"/>',
            '</g>')
    return svg.render()


# ---------------------------------------------------------------- carte d'activité

QUERY = '''query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes { name isFork languages(first: 12, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
    }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}'''

# Langages : mes dépôts publics, sans les copies de projets d'autres personnes ni les essais.
SKIP_REPOS = {'atheon006', 'interactive-designer-portfolio', 'pypresence', 'test-2004'}
# Forks réécrits au point d'être les miens.
OWN_FORKS = {'ecoleparent'}

MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
MONTHS_LONG = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
GOMA = dt.timezone(dt.timedelta(hours=2))


def fetch_github():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        sys.exit('GITHUB_TOKEN manquant')
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode(),
        headers={'Authorization': f'bearer {token}', 'Content-Type': 'application/json', 'User-Agent': f'{USER}-profile'},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get('errors'):
        sys.exit(f'Erreur GraphQL : {payload["errors"]}')
    return payload['data']['user']


def language_shares(repos, top=6):
    """Part de chaque langage : chaque dépôt pèse selon la racine carrée de sa taille,
    pour qu'un seul gros dépôt n'écrase pas tous les autres."""
    totals, colors = {}, {}
    for repo in repos:
        if repo['name'] in SKIP_REPOS or (repo['isFork'] and repo['name'] not in OWN_FORKS):
            continue
        edges = repo['languages']['edges']
        size = sum(e['size'] for e in edges)
        if not size:
            continue
        weight = math.sqrt(size)
        for e in edges:
            name = e['node']['name']
            colors[name] = e['node']['color'] or '#8a8a93'
            totals[name] = totals.get(name, 0) + weight * e['size'] / size
    total = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    shares = [(n, v / total, colors[n]) for n, v in ranked[:top]]
    rest = sum(v for _, v in ranked[top:]) / total
    if rest > 0.005:
        shares.append(('Autres', rest, None))
    return shares


def streaks(days):
    counts = [d['contributionCount'] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # la journée n'est pas finie
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return current, longest


def monotone_path(pts):
    """Courbe lisse qui ne dépasse pas les points (interpolation monotone de Fritsch-Carlson)."""
    n = len(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    if n < 3:
        return 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [(d[i - 1] + d[i]) / 2 if d[i - 1] * d[i] > 0 else 0 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        s = a * a + b * b
        if s > 9:
            k = 3 / math.sqrt(s)
            m[i], m[i + 1] = k * a * d[i], k * b * d[i]
    path = f'M{xs[0]:.1f},{ys[0]:.1f}'
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        path += (f' C{xs[i] + h / 3:.1f},{ys[i] + m[i] * h / 3:.1f} '
                 f'{xs[i + 1] - h / 3:.1f},{ys[i + 1] - m[i + 1] * h / 3:.1f} {xs[i + 1]:.1f},{ys[i + 1]:.1f}')
    return path


def fmt(n):
    return f'{n:,}'.replace(',', ' ')


def activity(data, t, now):
    cc = data['contributionsCollection']
    all_weeks = cc['contributionCalendar']['weeks']
    created = dt.date.fromisoformat(data['createdAt'][:10])
    first_week = next((i for i, w in enumerate(all_weeks)
                       if dt.date.fromisoformat(w['contributionDays'][-1]['date']) >= created), 0)
    since_creation = first_week > 0 and len(all_weeks) - first_week >= 8
    weeks = all_weeks[first_week:] if since_creation else all_weeks
    days = [d for w in all_weeks for d in w['contributionDays']]
    current, longest = streaks(days)
    shares = language_shares(data['repositories']['nodes'])

    W, pad = 1000, 36
    svg = Svg(W, 10, '')
    svg.css.append(MOTION_CSS + REDUCED_CSS)
    svg.css.append('@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}'
                   f'.draw{{stroke-dasharray:1;stroke-dashoffset:0;animation:draw 1.8s {EASE} both .25s}}'
                   '@keyframes grow{from{transform:scaleX(0)}to{transform:none}}'
                   f'.grow{{transform-origin:{pad}px 0;animation:grow 1.2s {EASE} both .5s}}'
                   '.area{animation:fade 1.4s ease both .6s}')

    # En-tête
    period = f'DEPUIS {MONTHS_LONG[created.month - 1].upper()} {created.year}' if since_creation else '12 DERNIERS MOIS'
    head = [svg.text(pad, 58, 'Activité sur GitHub', 20, 'sans', 600, t['fg'], tracking=-0.01),
            svg.text(W - pad, 57, period, 11.5, 'mono', 500, t['dim'], 'end', 0.14)]

    # Chiffres clés
    figures = [
        (fmt(cc['contributionCalendar']['totalContributions']), '', 'contributions'),
        (fmt(cc['totalCommitContributions']), '', 'commits'),
        (fmt(cc['totalPullRequestContributions']), '', 'pull requests'),
        (fmt(current), ' j', 'série en cours'),
        (fmt(longest), ' j', 'record de série'),
        (fmt(data['followers']['totalCount']), '', 'abonnés'),
    ]
    col = (W - pad * 2) / len(figures)
    figs = []
    for i, (value, unit, label) in enumerate(figures):
        x = pad + i * col + (18 if i else 0)
        if i:
            figs.append(f'<path d="M{pad + i * col:.1f} 92V154" stroke="{t["line"]}"/>')
        parts = [(value, 600, t['fg'], None)] + ([(unit, 500, t['dim'], 20)] if unit else [])
        figs.append(f'<g class="up" style="--d:{.05 + i * .06:.2f}s">'
                    + svg.spans(x, 128, parts, 34, 'sans', cls='tn', extra='letter-spacing="-1"')
                    + svg.text(x, 151, label, 13, 'sans', 400, t['dim']) + '</g>')

    # Courbe hebdomadaire
    top, bottom = 200, 300
    totals = [sum(d['contributionCount'] for d in w['contributionDays']) for w in weeks]
    peak = max(totals) or 1
    step = (W - pad * 2) / max(len(totals) - 1, 1)
    pts = [(pad + i * step, bottom - (v / peak) * (bottom - top)) for i, v in enumerate(totals)]
    line = monotone_path(pts)
    svg.defs.append(f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["accent"]}" stop-opacity=".28"/>'
                    f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></linearGradient>')
    chart = [f'<path d="M{pad} {bottom}H{W - pad}" stroke="{t["line"]}"/>',
             f'<path class="area" d="{line} L{pts[-1][0]:.1f},{bottom} L{pts[0][0]:.1f},{bottom} Z" fill="url(#area)"/>',
             f'<path class="draw" d="{line}" pathLength="1" fill="none" stroke="{t["accent"]}" stroke-width="2.2" '
             'stroke-linecap="round" stroke-linejoin="round"/>']
    pi = max(range(len(totals)), key=lambda i: totals[i])
    px, py = pts[pi]
    tip = f'record : {fmt(totals[pi])} en une semaine'
    anchor = 'end' if px > W - 220 else 'start' if px < 220 else 'middle'
    chart += [f'<g class="up" style="--d:1.6s"><circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="{t["accent"]}" fill-opacity=".18"/>'
              f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.6" fill="{t["accent"]}"/>',
              svg.text(px + (10 if anchor == 'start' else -10 if anchor == 'end' else 0), py - 14, tip, 11.5, 'mono', 500, t['ink'], anchor),
              '</g>']
    last_x, prev_month = -100, None
    for i, w in enumerate(weeks):
        d0 = dt.date.fromisoformat(w['contributionDays'][0]['date'])
        if d0.month != prev_month and i:
            x = pad + i * step
            if x - last_x > 46 and x < W - pad - 20:
                chart.append(svg.text(x, bottom + 22, MONTHS[d0.month - 1], 11, 'mono', 400, t['dim'], 'middle'))
                chart.append(f'<path d="M{x:.1f} {bottom}v4" stroke="{t["line2"]}"/>')
                last_x = x
        prev_month = d0.month

    # Langages
    ly = 360
    langs = [svg.text(pad, ly, 'LANGAGES · DÉPÔTS PUBLICS', 11.5, 'mono', 500, t['dim'], tracking=0.14)]
    bar_y, bar_w = ly + 16, W - pad * 2
    svg.defs.append(f'<clipPath id="bar"><rect x="{pad}" y="{bar_y}" width="{bar_w}" height="10" rx="5"/></clipPath>')
    segs, x = [], pad
    for name, share, color in shares:
        w = share * bar_w
        segs.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + .5:.2f}" height="10" fill="{color or t["dim"]}"/>')
        x += w
    langs.append(f'<rect x="{pad}" y="{bar_y}" width="{bar_w}" height="10" rx="5" fill="{t["track"]}"/>'
                 f'<g clip-path="url(#bar)"><g class="grow">{"".join(segs)}</g></g>')
    lx, lyy = pad, bar_y + 38
    for name, share, color in shares:
        pct = f'{share * 100:.1f} %'.replace('.', ',')
        name_w = text_width(name, 13, 'sans', 500)
        item_w = 14 + name_w + 7 + text_width(pct, 12, 'mono', 400) + 26
        if lx + item_w > W - pad:
            lx, lyy = pad, lyy + 26
        langs += [f'<circle cx="{lx + 4}" cy="{lyy - 4.5}" r="4" fill="{color or t["dim"]}"/>',
                  svg.text(lx + 14, lyy, name, 13, 'sans', 500, t['fg']),
                  svg.text(lx + 14 + name_w + 7, lyy, pct, 12, 'mono', 400, t['dim'])]
        lx += item_w

    H = lyy + 46
    stamp = f'mis à jour le {now.day} {MONTHS[now.month - 1]} {now.year}'
    foot = svg.text(W - pad, H - 20, stamp, 11, 'mono', 400, t['dim'], 'end')
    svg.h = H
    svg.title = (f'Activité GitHub de Ready Kalonda : {figures[0][0]} contributions, {figures[1][0]} commits, '
                 f'record de série {longest} jours. Langages : ' + ', '.join(n for n, _, _ in shares) + '.')
    svg.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="{t["panel"]}" stroke="{t["line"]}"/>',
            *head, *figs, *chart, '<g class="up" style="--d:.4s">', *langs, '</g>', foot)
    return svg.render()


# ---------------------------------------------------------------- point d'entrée

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'{path}  {len(content.encode()) // 1024} Ko')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'static'
    if cmd == 'static':
        write(f'{ASSETS}/banner.svg', banner())
        write(f'{ASSETS}/contact.svg', contact())
        for theme, t in THEMES.items():
            write(f'{ASSETS}/stack-{theme}.svg', stack(t))
            for key, label, brand, primary in LINKS:
                write(f'{ASSETS}/links/{key}-{theme}.svg', button(label, brand, primary, t))
            for status in ('live', 'beta', 'proto'):
                write(f'{ASSETS}/badges/{status}-{theme}.svg', badge(status, t))
    elif cmd == 'stats':
        out = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else 'dist')
        data = fetch_github()
        now = dt.datetime.now(GOMA)
        for theme, t in THEMES.items():
            write(os.path.join(out, f'stats-{theme}.svg'), activity(data, t, now))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
