//! NeXXUs storage daemon (nexxusd).
//! Phase 6: redb persistent chunk index; networking/storage wire in Phase 7.

use std::env;
use std::process;

mod storage;
mod tor;
use storage::ChunkStore;

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: nexxusd <store-path>");
        process::exit(2);
    });

    match ChunkStore::open(&path) {
        Ok(_store) => println!(
            "nexxusd {} — redb chunk store opened at {}",
            env!("CARGO_PKG_VERSION"),
            path
        ),
        Err(e) => {
            eprintln!("nexxusd: failed to open store: {e}");
            process::exit(1);
        }
    }
}
