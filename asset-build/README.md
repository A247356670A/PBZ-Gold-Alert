# Supporting asset/development source

Current snapshot: development V2.0.5, distributed unchanged as Official V2.0 Combined.

The root `BUILD.md` documents the reproducible Installer `-BuildOnly` route. This directory contains the Python code used for asset changes and packaging, with its local Python import dependencies and retained third-party notices. It does not include proprietary game/audio assets, game keys, mapping files, tool binaries or the required raw build intermediates.

Current final builder: `work/build_gold_alert_v205.py`.
Combined release exporter: `work/export_official_v20_combined.py`.
Gauntlet contact/sound hooks: `work/gauntlet_trigger_v1610.py`, `work/parry_success_hook_v1612.py`.
Final Sha Chi logic: `work/shachi_fixed_v205.py`.
Success-audio gain: `work/success_pcm_v202.py`, `work/success_pcm_v203.py`.
Pale-gold FX: `work/counter_gold_v202.py`, `work/followup_gold_v203.py`, `work/punch_gold_v204.py`.

Historical builders and the old split exporter are retained as dependencies/history, not alternate current packages. Some builder entry points install after building; read them before execution. Do not run them as a compilation-only test.
