/// PyO3 native extension for Nexus3D Vault.
///
/// Exposes two functions:
/// - ``gcode_scan(path: str) -> dict``  — combined sha256 + metadata + thumbnail
/// - ``rasterise(tri, shade, width, height) -> bytes``  — parallel triangle rasteriser

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

mod gcode;
mod raster;

// ---------------------------------------------------------------------------
// gcode_scan — Python entry point
// ---------------------------------------------------------------------------

#[pyfunction]
fn gcode_scan(py: Python<'_>, path: &str) -> PyResult<Py<PyDict>> {
    let result = crate::gcode::gcode_scan(std::path::Path::new(path))
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

    let dict = PyDict::new(py);
    dict.set_item("sha256", &result.sha256)?;

    let meta = &result.meta;
    let set = |dict: &Bound<'_, PyDict>, key: &str, val: &dyn std::fmt::Display| {
        dict.set_item(key, val.to_string())
    };

    let set_opt_str = |dict: &Bound<'_, PyDict>, key: &str, val: &Option<String>| {
        match val {
            Some(v) => dict.set_item(key, v.as_str()),
            None => dict.set_item(key, py.None()),
        }
    };
    let set_opt_i64 = |dict: &Bound<'_, PyDict>, key: &str, val: Option<i64>| {
        match val {
            Some(v) => dict.set_item(key, v),
            None => dict.set_item(key, py.None()),
        }
    };
    let set_opt_f64 = |dict: &Bound<'_, PyDict>, key: &str, val: Option<f64>| {
        match val {
            Some(v) => dict.set_item(key, v),
            None => dict.set_item(key, py.None()),
        }
    };

    set_opt_str(&dict, "slicer_name", &meta.slicer_name)?;
    set_opt_str(&dict, "slicer_version", &meta.slicer_version)?;
    set_opt_str(&dict, "printer_model", &meta.printer_model)?;
    set_opt_f64(&dict, "nozzle_diameter_mm", meta.nozzle_diameter_mm)?;
    set_opt_f64(&dict, "layer_height_mm", meta.layer_height_mm)?;
    set_opt_f64(&dict, "infill_percent", meta.infill_percent)?;
    set_opt_i64(&dict, "estimated_time_s", meta.estimated_time_s)?;
    set_opt_f64(&dict, "filament_weight_g", meta.filament_weight_g)?;
    set_opt_f64(&dict, "filament_length_mm", meta.filament_length_mm)?;
    set_opt_f64(&dict, "filament_cost", meta.filament_cost)?;
    set_opt_str(&dict, "material_type", &meta.material_type)?;

    match &result.thumbnail_png {
        Some(png) => dict.set_item("thumbnail_png", PyBytes::new(py, png))?,
        None => dict.set_item("thumbnail_png", py.None())?,
    }

    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// rasterise — Python entry point
// ---------------------------------------------------------------------------

#[pyfunction]
fn rasterise(
    tri: Vec<f64>,
    shade: Vec<f64>,
    width: u32,
    height: u32,
) -> PyResult<Py<PyBytes>> {
    let buf = crate::raster::rasterise(&tri, &shade, width, height);
    Python::with_gil(|py| Ok(PyBytes::new(py, &buf).into()))
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

#[pymodule]
fn _nexus3d_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(gcode_scan, m)?)?;
    m.add_function(wrap_pyfunction!(rasterise, m)?)?;
    Ok(())
}
