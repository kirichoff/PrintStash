/// PyO3 native extension for Nexus3D Vault.
///
/// Exposes two functions:
/// - ``gcode_scan(path: str) -> dict``  — combined sha256 + metadata + thumbnail
/// - ``rasterise(tri, shade, width, height) -> bytes``  — parallel triangle rasteriser

use pyo3::prelude::*;
use pyo3::types::PyDict;

mod gcode;
mod raster;

// ---------------------------------------------------------------------------
// gcode_scan — Python entry point
// ---------------------------------------------------------------------------

#[pyfunction]
fn gcode_scan(py: Python<'_>, path: &str) -> PyResult<Py<PyDict>> {
    let result = crate::gcode::gcode_scan(std::path::Path::new(path))
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

    let dict = PyDict::new(py);
    dict.set_item("sha256", result.sha256)?;

    let meta = result.meta;
    // Use None for missing fields so Python consumers get None, not absent keys.
    let none = || py.None();

    let set_opt = |key: &str, val: Option<String>| -> PyResult<()> {
        dict.set_item(key, val.map_or_else(none, |v| v.into_py(py)))?;
        Ok(())
    };
    let set_opt_int = |key: &str, val: Option<i64>| -> PyResult<()> {
        dict.set_item(key, val.map_or_else(none, |v| v.into_py(py)))?;
        Ok(())
    };
    let set_opt_float = |key: &str, val: Option<f64>| -> PyResult<()> {
        dict.set_item(key, val.map_or_else(none, |v| v.into_py(py)))?;
        Ok(())
    };

    set_opt("slicer_name", meta.slicer_name)?;
    set_opt("slicer_version", meta.slicer_version)?;
    set_opt("printer_model", meta.printer_model)?;
    set_opt_float("nozzle_diameter_mm", meta.nozzle_diameter_mm)?;
    set_opt_float("layer_height_mm", meta.layer_height_mm)?;
    set_opt_float("infill_percent", meta.infill_percent)?;
    set_opt_int("estimated_time_s", meta.estimated_time_s)?;
    set_opt_float("filament_weight_g", meta.filament_weight_g)?;
    set_opt_float("filament_length_mm", meta.filament_length_mm)?;
    set_opt_float("filament_cost", meta.filament_cost)?;
    set_opt("material_type", meta.material_type)?;

    dict.set_item(
        "thumbnail_png",
        result
            .thumbnail_png
            .map_or_else(none, |v| pyo3::types::PyBytes::new(py, &v).into_py(py)),
    )?;

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
) -> PyResult<pyo3::types::Py<pyo3::types::PyBytes>> {
    let buf = crate::raster::rasterise(&tri, &shade, width, height);
    Python::with_gil(|py| Ok(pyo3::types::PyBytes::new(py, &buf).into()))
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
