//! wasm-bindgen surface for the browser panel. Bindings land in Phase 7 (ADR plan §Фаза 7).

pub use nexxus_core;

/// Placeholder so the workspace builds; real exports are added with wasm-bindgen in Phase 7.
pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
