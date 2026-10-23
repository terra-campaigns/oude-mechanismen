#!/usr/bin/env python3
"""
art_filter.py - Generic Graphic-Novel Art Filter Engine
Part of the illustrate-entry skill in oude-mechanismen.

Transforms archival cultural photography and period imagery into stylized
graphic-novel illustrations matching campaign aesthetic profiles.
"""

import argparse
import math
import os
import sys
import urllib.request
import urllib.parse
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
import yaml

DEFAULT_FALLBACK_PRESETS = {
    "graphic_novel": {
        "label": "Classic Graphic Novel",
        "description": "Bold ink contours with warm parchment and copper sepia wash.",
        "ramp": [
            [0.00, "#120c08"],
            [0.30, "#542d18"],
            [0.60, "#ba7336"],
            [0.85, "#e8be78"],
            [1.00, "#fcf7eb"]
        ],
        "bg_ramp": [
            [0.00, "#232b30"],
            [0.50, "#4a6875"],
            [1.00, "#dde9ec"]
        ],
        "inking": {"sigma1": 1.0, "sigma2": 2.8, "threshold": 2.2, "span": 5.0},
        "chromatic_aberration": 3
    }
}


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return np.array([int(hex_str[i:i+2], 16) for i in (0, 2, 4)], dtype=np.float32)


def create_color_ramp(stops, length=256):
    """
    Interpolates a list of [position, hex_color] stops into a (256, 3) float32 RGB ramp.
    """
    ramp = np.zeros((length, 3), dtype=np.float32)
    positions = [float(s[0]) for s in stops]
    colors = [hex_to_rgb(s[1]) for s in stops]

    for i in range(length):
        t = i / (length - 1)
        if t <= positions[0]:
            ramp[i] = colors[0]
        elif t >= positions[-1]:
            ramp[i] = colors[-1]
        else:
            for j in range(len(positions) - 1):
                if positions[j] <= t <= positions[j+1]:
                    span = positions[j+1] - positions[j]
                    local_t = (t - positions[j]) / (span if span > 0 else 1.0)
                    ramp[i] = (1.0 - local_t) * colors[j] + local_t * colors[j+1]
                    break
    return ramp


def apply_gradient_map(gray_norm, ramp):
    """
    Maps normalised grayscale values (0..255) through an RGB colour ramp.
    """
    indices = np.clip(gray_norm.astype(int), 0, 255)
    return ramp[indices]


def extract_comic_ink_lines(img_gray, sigma1=1.0, sigma2=2.8, threshold=2.2, span=5.0):
    """
    Extracts crisp, organic ink line-art using Difference of Gaussians (DoG).
    Returns (H, W) float in 0.0 (ink black) to 1.0 (paper/colour passes through).
    """
    g1 = img_gray.filter(ImageFilter.GaussianBlur(sigma1))
    g2 = img_gray.filter(ImageFilter.GaussianBlur(sigma2))

    a1 = np.array(g1, dtype=np.float32)
    a2 = np.array(g2, dtype=np.float32)

    edge = np.abs(a1 - a2)
    ink = 1.0 - np.clip((edge - threshold) / span, 0.0, 1.0)
    return ink


def create_radial_burst(width, height, center_x, center_y, num_rays=24, ray_contrast=0.4):
    """
    Creates a radial sunburst pattern emanating from a focal point.
    """
    y, x = np.ogrid[:height, :width]
    angles = np.arctan2(y - center_y, x - center_x)
    rays = 0.5 + 0.5 * np.sin(angles * num_rays)
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    max_d = math.hypot(width, height)
    norm_dist = np.clip(dist / (max_d * 0.7), 0.0, 1.0)

    pattern = 0.5 + 0.5 * rays * (1.0 - 0.3 * norm_dist)
    return pattern.astype(np.float32)


def apply_chromatic_aberration(rgb_arr, shift_pixels=6):
    """
    Splits and shifts Red and Blue channels horizontally for vintage optical fringe.
    """
    if shift_pixels <= 0:
        return rgb_arr
    h, w, c = rgb_arr.shape
    out = np.copy(rgb_arr)
    out[:, shift_pixels:, 0] = rgb_arr[:, :-shift_pixels, 0]
    out[:, :-shift_pixels, 2] = rgb_arr[:, shift_pixels:, 2]
    return out


def apply_liquid_wave_distortion(rgb_arr, amplitude=7.0, wavelength=100.0):
    """
    Applies sinusoidal mesh displacement for heat mirage / hallucinatory ripple.
    """
    if amplitude <= 0:
        return rgb_arr
    h, w, c = rgb_arr.shape
    y_coords, x_coords = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')

    x_shift = (amplitude * np.sin(2.0 * np.pi * y_coords / wavelength)).astype(np.int32)
    new_x = np.clip(x_coords + x_shift, 0, w - 1)

    return rgb_arr[y_coords, new_x]


def draw_lens_flare(draw, x, y, size=120, color=(255, 255, 255), num_spikes=8):
    """
    Renders a multi-tiered diffraction lens flare with halation and needle spikes.
    """
    for r in range(size, 0, -8):
        alpha = int(140 * (1.0 - r / size)**1.4)
        bbox = [x - r, y - r, x + r, y + r]
        draw.ellipse(bbox, fill=tuple(color) + (alpha,))

    spike_len = size * 2.4
    for i in range(num_spikes):
        angle = i * (math.pi / (num_spikes / 2.0))
        dx = math.cos(angle)
        dy = math.sin(angle)

        p1 = (x + dx * spike_len, y + dy * spike_len)
        perp_dx = -dy * 3.5
        perp_dy = dx * 3.5
        p2 = (x + perp_dx, y + perp_dy)
        p3 = (x - dx * (spike_len * 0.15), y - dy * (spike_len * 0.15))
        p4 = (x - perp_dx, y - perp_dy)
        draw.polygon([p1, p2, p3, p4], fill=tuple(color) + (210,))


def load_image(input_source):
    """
    Loads an image from a local path or remote URL.
    """
    if input_source.startswith("http://") or input_source.startswith("https://"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) illustrate-entry/1.0"
        }
        req = urllib.request.Request(input_source, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return Image.open(resp).convert("RGB")
    else:
        if not os.path.exists(input_source):
            raise FileNotFoundError(f"Input image not found: {input_source}")
        return Image.open(input_source).convert("RGB")


def load_config(config_path=None):
    """
    Locates and loads aesthetic configuration YAML.
    """
    candidate_paths = [
        config_path,
        os.path.join(".agents", "context", "aesthetics.yml"),
        os.path.join("..", ".agents", "context", "aesthetics.yml"),
    ]
    for p in candidate_paths:
        if p and os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "presets" in data:
                    return data
    return {"name": "Default", "presets": DEFAULT_FALLBACK_PRESETS}


def detect_focal_points(gray_np, max_points=4):
    """
    Detects prominent bright specular highlights / eye ports / oculars in top half.
    """
    h, w = gray_np.shape
    top_region = gray_np[:int(h * 0.45), :]
    threshold = np.percentile(top_region, 96)
    
    # Locate candidate clusters
    peaks = []
    step_y = max(10, int(h * 0.02))
    step_x = max(10, int(w * 0.02))
    for y in range(0, top_region.shape[0] - step_y, step_y):
        for x in range(0, top_region.shape[1] - step_x, step_x):
            block = top_region[y:y+step_y, x:x+step_x]
            if block.max() > threshold:
                by, bx = np.unravel_index(np.argmax(block), block.shape)
                peaks.append((x + bx, y + by, float(block.max())))
                
    peaks = sorted(peaks, key=lambda p: p[2], reverse=True)
    focal = []
    for px, py, pval in peaks:
        if not any(math.hypot(px - fx, py - fy) < step_x * 2.5 for fx, fy in focal):
            focal.append((px, py))
            if len(focal) >= max_points:
                break
    return focal


def process_image(img, preset_name, preset_cfg, focal_points=None, separate_matte=True):
    """
    Renders a single aesthetic preset on an image.
    """
    w, h = img.size
    gray = img.convert('L')
    gray_np = np.array(gray, dtype=np.float32)

    # Inking parameters
    ink_cfg = preset_cfg.get("inking", {})
    s1 = ink_cfg.get("sigma1", 1.0)
    s2 = ink_cfg.get("sigma2", 2.8)
    thresh = ink_cfg.get("threshold", 2.2)
    span = ink_cfg.get("span", 5.0)

    ink_lines = extract_comic_ink_lines(gray, sigma1=s1, sigma2=s2, threshold=thresh, span=span)
    ink_lines_3c = np.stack([ink_lines]*3, axis=-1)

    # Normalise foreground tonal range
    subject_norm = np.clip((gray_np - 12.0) / 115.0, 0.0, 1.0) * 255.0

    # Ramps
    ramp = create_color_ramp(preset_cfg["ramp"])
    subject_col = apply_gradient_map(subject_norm, ramp)

    if separate_matte and "bg_ramp" in preset_cfg:
        # Separate foreground subject from lighter museum/studio backdrop
        matte_raw = np.clip((148.0 - gray_np) / 35.0, 0.0, 1.0)
        matte_img = Image.fromarray((matte_raw * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
        matte = np.array(matte_img, dtype=np.float32) / 255.0
        matte_3c = np.stack([matte]*3, axis=-1)

        # Background radial burst pattern
        cx, cy = focal_points[0] if (focal_points and len(focal_points) > 0) else (w // 2, h // 3)
        burst_cfg = preset_cfg.get("radial_burst", {})
        num_rays = burst_cfg.get("num_rays", 24)
        contrast = burst_cfg.get("ray_contrast", 0.35)
        bg_pattern = create_radial_burst(w, h, cx, cy, num_rays=num_rays, ray_contrast=contrast)

        bg_ramp = create_color_ramp(preset_cfg["bg_ramp"])
        bg_col = apply_gradient_map(bg_pattern * 255.0, bg_ramp)

        comp = subject_col * matte_3c + bg_col * (1.0 - matte_3c)
    else:
        comp = subject_col

    # Apply comic ink lines
    comp = comp * ink_lines_3c
    comp = np.clip(comp, 0, 255).astype(np.uint8)

    # Liquid wave mirage distortion
    mirage_cfg = preset_cfg.get("mirage_wave")
    if mirage_cfg:
        comp = apply_liquid_wave_distortion(
            comp,
            amplitude=mirage_cfg.get("amplitude", 7.0),
            wavelength=mirage_cfg.get("wavelength", 100.0)
        )

    # Chromatic aberration
    chroma_shift = preset_cfg.get("chromatic_aberration", 0)
    if chroma_shift > 0:
        comp = apply_chromatic_aberration(comp, shift_pixels=chroma_shift)

    # Risograph stipple grain
    grain_sigma = preset_cfg.get("grain_sigma", 0.0)
    if grain_sigma > 0:
        np.random.seed(42)
        grain = np.random.normal(0, grain_sigma, (h, w, 3)).astype(np.float32)
        comp = np.clip(comp.astype(np.float32) + grain, 0, 255).astype(np.uint8)

    # Flares and specular glints
    flare_cfg = preset_cfg.get("flares")
    if flare_cfg and flare_cfg.get("enabled", False) and focal_points:
        flare_layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(flare_layer)
        primary_cx, primary_cy = focal_points[0]

        # 360-degree ocular beams if configured
        if flare_cfg.get("ocular_beams", False):
            beam_count = flare_cfg.get("beam_count", 24)
            for angle_deg in range(0, 360, int(360 / beam_count)):
                rad = math.radians(angle_deg)
                beam_len = w * 0.45
                bx = primary_cx + math.cos(rad) * beam_len
                by = primary_cy + math.sin(rad) * beam_len
                col = (0, 245, 255) if (angle_deg % (int(360 / beam_count) * 2) == 0) else (255, 30, 180)
                d.line([(primary_cx, primary_cy), (bx, by)], fill=col + (110,), width=3)

        # Primary flare
        size = flare_cfg.get("size", 120)
        color = flare_cfg.get("color", [255, 255, 255])
        spikes = flare_cfg.get("spikes", 8)
        draw_lens_flare(d, primary_cx, primary_cy, size=size, color=color, num_spikes=spikes)

        # Secondary glints on other focal points
        for fx, fy in focal_points[1:]:
            draw_lens_flare(d, fx, fy, size=int(size * 0.35), color=(255, 200, 230), num_spikes=4)

        out_img = Image.fromarray(comp).convert('RGBA')
        out_img = Image.alpha_composite(out_img, flare_layer).convert('RGB')
        return out_img

    return Image.fromarray(comp).convert('RGB')


def main():
    parser = argparse.ArgumentParser(description="Generic graphic-novel art filter for campaign wiki imagery.")
    parser.add_argument("--input", "-i", required=True, help="Path to input image file or direct image URL.")
    parser.add_argument("--config", "-c", help="Path to campaign aesthetics.yml configuration.")
    parser.add_argument("--preset", "-p", default="all", help="Preset name to render, or 'all' for all presets.")
    parser.add_argument("--output-dir", "-o", help="Output directory for generated images.")
    parser.add_argument("--name-prefix", "-n", help="Prefix for output file names.")
    parser.add_argument("--target-width", type=int, default=1400, help="Working resolution width in pixels.")
    parser.add_argument("--no-matte", action="store_true", help="Do not separate foreground subject from backdrop.")
    parser.add_argument("--flare-coords", help="Explicit focal coordinates as 'x,y' for flare placement.")

    args = parser.parse_args()

    # Load configuration
    cfg = load_config(args.config)
    presets = cfg.get("presets", DEFAULT_FALLBACK_PRESETS)

    # Determine output directory
    out_dir = args.output_dir or cfg.get("default_output_dir", "imgs/gallery")
    os.makedirs(out_dir, exist_ok=True)

    # Load and prepare image
    print(f"Loading input: {args.input}")
    orig_img = load_image(args.input)
    orig_w, orig_h = orig_img.size

    # Resize to target working width
    target_w = args.target_width
    target_h = int(orig_h * (target_w / orig_w))
    working_img = orig_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    print(f"Working resolution: {target_w}x{target_h}")

    # Determine focal points
    gray_np = np.array(working_img.convert('L'), dtype=np.float32)
    if args.flare_coords:
        scale = target_w / float(orig_w)
        focal_points = []
        for pair in args.flare_coords.split(';'):
            if ',' in pair:
                fx, fy = [float(v.strip()) for v in pair.split(',')]
                focal_points.append((int(fx * scale), int(fy * scale)))
    else:
        focal_points = detect_focal_points(gray_np)
    print(f"Focal / flare origins: {focal_points}")

    # Base name for outputs
    if args.name_prefix:
        base_name = args.name_prefix
    else:
        base_name = os.path.splitext(os.path.basename(args.input.split("?")[0]))[0]
        base_name = base_name.replace(" ", "_").lower()

    # Render selected presets
    selected_keys = presets.keys() if args.preset == "all" else [args.preset]
    rendered_files = []

    for key in selected_keys:
        if key not in presets:
            print(f"Warning: Preset '{key}' not found in configuration. Skipping.")
            continue
        p_cfg = presets[key]
        print(f"Rendering preset: {key} ({p_cfg.get('label', key)})...")
        rendered = process_image(
            working_img,
            key,
            p_cfg,
            focal_points=focal_points,
            separate_matte=not args.no_matte
        )
        out_filename = f"{base_name}_{key}.jpg"
        out_path = os.path.join(out_dir, out_filename)
        rendered.save(out_path, quality=95)
        rendered_files.append((key, out_path))
        print(f"  -> Saved: {out_path}")

    print(f"\nCompleted: {len(rendered_files)} filtered asset(s) rendered to {out_dir}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
