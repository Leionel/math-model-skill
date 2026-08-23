// ARCHIVE — Phase 2.5 standalone freeze spike (historically mounted as mmfrz-3/pkg-3).
//
// SUPERSEDED by checkpoint.host.js (the consolidated Phase 3 host package):
// `harness_freeze_results` now lives there so the freeze call also records the
// project root that feeds the mm-progress / mm-evidence panel RPCs. Mounting
// this archive package alongside checkpoint.host.js would double-register the
// tool, so this file intentionally registers nothing. Keep it only as the
// historical record of the Phase 2.5 acceptance (see ../native/README.md).
return {
  inject: [],
  apply() {
    // no-op: superseded by checkpoint.host.js
  },
}
