//! wasm-bindgen surface for the browser panel.
//! Real wasm-bindgen exports are added with the UI build (separate track).
//! Placeholder so the workspace builds.

pub use nexxus_core;

/// Placeholder version string.
pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
