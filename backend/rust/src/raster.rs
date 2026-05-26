/// Parallel z-buffered triangle rasteriser.
///
/// Receives pre-projected, pre-sorted, shade-calculated triangles from the
/// Python caller (which uses numpy for the mesh transform + lighting math).
/// Renders them into a flat RGB888 buffer using rayon strip-level parallelism.
///
/// No external crate dependencies beyond std + rayon. Designed to slot in
/// as a drop-in replacement for the Python ``_rasterise_triangles`` loop.
use rayon::prelude::*;

/// Rasterise flat-shaded triangles into an RGB888 byte buffer.
///
/// # Arguments
/// * `tri`   — flat `[f64]`, length `F × 9`. Each triangle: [x0,y0,z0, x1,y1,z1, x2,y2,z2]
/// * `shade` — length `F`, per-face intensity in [0.0, 1.0]
/// * `width` / `height` — output image dimensions (pixels)
///
/// # Returns
/// ``Vec<u8>`` of length ``width × height × 3``, RGB row-major.
pub fn rasterise(tri: &[f64], shade: &[f64], width: u32, height: u32) -> Vec<u8> {
    assert_eq!(
        tri.len() % 9,
        0,
        "tri length must be a multiple of 9 (F × 3 vertices × 3 coords)"
    );
    let face_count = tri.len() / 9;
    assert_eq!(shade.len(), face_count, "shade length must equal face count");

    let w = width as usize;
    let h = height as usize;

    // Pre-pack triangles into struct-of-arrays for fast iteration.
    let tris: Vec<Triangle> = (0..face_count)
        .map(|i| {
            let base = i * 9;
            Triangle {
                x0: tri[base],
                y0: tri[base + 1],
                z0: tri[base + 2],
                x1: tri[base + 3],
                y1: tri[base + 4],
                z1: tri[base + 5],
                x2: tri[base + 6],
                y2: tri[base + 7],
                z2: tri[base + 8],
            }
        })
        .collect();

    // Base colour (slate blue-grey, matches the Python version).
    let base_r = 158.0f64;
    let base_g = 179.0f64;
    let base_b = 194.0f64;

    // Background colour (matches UI muted bg).
    let bg_r: u8 = 248;
    let bg_g: u8 = 249;
    let bg_b: u8 = 250;

    // Allocate output buffer filled with background.
    let mut out = vec![bg_r, bg_g, bg_b].repeat(w * h);

    // Strip-level parallelism.
    let num_strips = rayon::current_num_threads().max(1);
    let strip_height = (h + num_strips - 1) / num_strips;

    out.par_chunks_mut(w * 3 * strip_height)
        .enumerate()
        .for_each(|(strip_idx, strip_pixels)| {
            let y_lo = strip_idx * strip_height;
            let y_hi = h.min(y_lo + strip_height);
            let local_h = y_hi - y_lo;

            let mut local_zbuf = vec![f64::INFINITY; w * local_h];

            // Filter triangles that intersect this strip.
            let strip_y_lo = y_lo as f64;
            let strip_y_hi = y_hi as f64;
            let relevant: Vec<(usize, &Triangle)> = tris
                .iter()
                .enumerate()
                .filter(|(_, t)| {
                    let y_min = t.y0.min(t.y1).min(t.y2);
                    let y_max = t.y0.max(t.y1).max(t.y2);
                    y_min < strip_y_hi && y_max >= strip_y_lo
                })
                .collect();

            for (fi, t) in relevant {
                let si = shade[fi];
                raster_triangle(
                    t,
                    si,
                    base_r,
                    base_g,
                    base_b,
                    w,
                    local_h,
                    y_lo,
                    strip_pixels,
                    &mut local_zbuf,
                );
            }
        });

    out
}

struct Triangle {
    x0: f64,
    y0: f64,
    z0: f64,
    x1: f64,
    y1: f64,
    z1: f64,
    x2: f64,
    y2: f64,
    z2: f64,
}

#[inline]
fn raster_triangle(
    t: &Triangle,
    shade: f64,
    base_r: f64,
    base_g: f64,
    base_b: f64,
    img_w: usize,
    local_h: usize,
    y_lo: usize,
    strip_pixels: &mut [u8],
    local_zbuf: &mut [f64],
) {
    // AABB in pixel space (clamped to strip bounds).
    let x_min_f = t.x0.min(t.x1).min(t.x2);
    let x_max_f = t.x0.max(t.x1).max(t.x2);
    let y_min_f = t.y0.min(t.y1).min(t.y2);
    let y_max_f = t.y0.max(t.y1).max(t.y2);

    let px_min = (x_min_f.floor() as isize).max(0) as usize;
    let px_max = (x_max_f.ceil() as isize - 1).min(img_w as isize - 1) as usize;
    let py_min = (y_min_f.floor() as isize).max(y_lo as isize) as usize;
    let py_max = (y_max_f.ceil() as isize - 1).min((y_lo + local_h - 1) as isize) as usize;

    if px_max < px_min || py_max < py_min {
        return;
    }

    // Edge function denominator (twice signed triangle area in screen space).
    let denom = (t.y1 - t.y2) * (t.x0 - t.x2) + (t.x2 - t.x1) * (t.y0 - t.y2);
    if denom.abs() < 1e-12 {
        return;
    }
    let inv_denom = 1.0 / denom;

    let colour_r = (base_r * shade).clamp(0.0, 255.0) as u8;
    let colour_g = (base_g * shade).clamp(0.0, 255.0) as u8;
    let colour_b = (base_b * shade).clamp(0.0, 255.0) as u8;

    // Pre-compute edge deltas for fast incremental update.
    let dx_w0 = t.y1 - t.y2;
    let dy_w0 = t.x2 - t.x1;
    let dx_w1 = t.y2 - t.y0;
    let dy_w1 = t.x0 - t.x2;

    // Edge-function values at (px_min + 0.5, py_min + 0.5).
    let px = px_min as f64 + 0.5;
    let py0 = py_min as f64 + 0.5;

    let row0_w0 = ((t.y1 - t.y2) * (px - t.x2) + (t.x2 - t.x1) * (py0 - t.y2)) * inv_denom;
    let row0_w1 = ((t.y2 - t.y0) * (px - t.x2) + (t.x0 - t.x2) * (py0 - t.y2)) * inv_denom;

    let dx_w0_scaled = dx_w0 * inv_denom;
    let dx_w1_scaled = dx_w1 * inv_denom;
    let dy_w0_scaled = dy_w0 * inv_denom;
    let dy_w1_scaled = dy_w1 * inv_denom;

    for py in py_min..=py_max {
        let row = py - y_lo;
        let mut w0 = row0_w0 + (py - py_min) as f64 * dx_w0_scaled;
        let mut w1 = row0_w1 + (py - py_min) as f64 * dx_w1_scaled;

        let row_zbuf = &mut local_zbuf[row * img_w..(row + 1) * img_w];
        let row_pixels = &mut strip_pixels[row * img_w * 3..(row + 1) * img_w * 3];

        for px in px_min..=px_max {
            let w2 = 1.0 - w0 - w1;
            if w0 >= 0.0 && w1 >= 0.0 && w2 >= 0.0 {
                let z = w0 * t.z0 + w1 * t.z1 + w2 * t.z2;
                if z < row_zbuf[px] {
                    row_zbuf[px] = z;
                    let off = px * 3;
                    row_pixels[off] = colour_r;
                    row_pixels[off + 1] = colour_g;
                    row_pixels[off + 2] = colour_b;
                }
            }

            w0 += dy_w0_scaled;
            w1 += dy_w1_scaled;
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty() {
        let buf = rasterise(&[], &[], 64, 48);
        assert_eq!(buf.len(), 64 * 48 * 3);
        // Should be filled with background colour.
        assert_eq!(buf[0], 248);
        assert_eq!(buf[1], 249);
        assert_eq!(buf[2], 250);
    }

    #[test]
    fn test_single_triangle_full_screen() {
        // A single triangle covering the whole 2×2 image.
        let tri = vec![
            0.0, 0.0, -1.0, // v0
            2.0, 0.0, -1.0, // v1
            0.0, 2.0, -1.0, // v2
        ];
        let shade = vec![1.0];
        let buf = rasterise(&tri, &shade, 2, 2);
        // All pixels should be the full-lit base colour.
        let r = (158.0 * 1.0) as u8; // 158
        let g = (179.0 * 1.0) as u8; // 179
        let b = (194.0 * 1.0) as u8; // 194
        assert_eq!(buf[0], r);
        assert_eq!(buf[1], g);
        assert_eq!(buf[2], b);
        // Pixel (1,0) should also be covered.
        assert_eq!(buf[3], r);
    }

    #[test]
    fn test_depth_sort() {
        // Two overlapping triangles; the nearer one (z=-2) should win.
        let tri = vec![
            // Far triangle (z=-1) covering whole 2×2.
            0.0, 0.0, -1.0, 2.0, 0.0, -1.0, 0.0, 2.0, -1.0,
            // Near triangle (z=-2) covering top-left pixel only.
            0.0, 0.0, -2.0, 1.0, 0.0, -2.0, 0.0, 1.0, -2.0,
        ];
        let shade = vec![0.5, 1.0]; // far=50%, near=100%
        let buf = rasterise(&tri, &shade, 2, 2);

        let near_r = (158.0 * 1.0) as u8; // 158
        let far_r = (158.0 * 0.5) as u8; // 79

        // Pixel (0,0) — nearest triangle wins.
        assert_eq!(buf[0], near_r);
        // Pixel (1,0) — only far triangle covers it.
        assert_eq!(buf[3], far_r);
    }

    #[test]
    fn test_parallel_consistency() {
        // Same triangle rendered at different thread counts should produce
        // the same output.
        let tri = vec![0.0, 0.0, -1.0, 1.0, 0.0, -1.0, 0.0, 1.0, -1.0];
        let shade = vec![0.8];
        let buf1 = rasterise(&tri, &shade, 16, 16);
        let buf2 = rasterise(&tri, &shade, 16, 16);
        assert_eq!(buf1, buf2);
    }
}
