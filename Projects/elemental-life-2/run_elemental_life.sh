#!/bin/bash
cd "$(dirname "$0")"
exec build/linux/x64/debug/bundle/life_elements_game "$@"
